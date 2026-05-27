"""
core/agent.py — Agentic Document QA Loop

Instead of a fixed Router→Generator pipeline, this module implements
a true agentic loop where the LLM autonomously decides which tools
to call and when, iterating until it has enough context to answer.

The agent has 3 tools:
  - get_document_metadata   → doc info (page count, filename, status)
  - get_document_structure   → hierarchical tree index for reasoning
  - get_page_content(pages)  → full text of specific pages (e.g. "3-5,8")

Flow:
  1. User query + conversation history + tool definitions → Groq
  2. If Groq returns tool_calls → execute tools, feed results back, loop
  3. If Groq returns text (no tools) → that's the final answer
  4. Safety: max AGENT_MAX_ITERATIONS loops
"""

import json
import logging
from typing import Any

from groq import BadRequestError, APIError
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception

from core.config import settings
from core.page_index import (
    get_groq_client,
    load_document_metadata,
    load_document_structure,
    get_page_content,
)
from core.models import AgentToolCall

logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────
# Tool Definitions (Groq Function Calling Schema)
# ──────────────────────────────────────────────
TOOL_DEFINITIONS = [
    {
        "type": "function",
        "function": {
            "name": "get_document_metadata",
            "description": "Get document metadata including page count, filename, indexing status, and timestamp. Call this first to understand the document.",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_document_structure",
            "description": "Get the document's hierarchical tree structure index (titles, summaries, page ranges). Use this to identify which sections/pages are most relevant to the user's question before fetching full page content.",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_page_content",
            "description": "Retrieve the full text content of specific pages. Use tight page ranges based on the document structure. Examples: '3-5' for pages 3 to 5, '3,8' for pages 3 and 8, '12' for just page 12. Maximum 8 pages per call.",
            "parameters": {
                "type": "object",
                "properties": {
                    "pages": {
                        "type": "string",
                        "description": "Page numbers or ranges to fetch. E.g. '3-5,8' or '1,4,7'",
                    }
                },
                "required": ["pages"],
            },
        },
    },
]


# ──────────────────────────────────────────────
# Agent System Prompt
# ──────────────────────────────────────────────
AGENT_SYSTEM_PROMPT = """You are Juris AI, an agentic legal document assistant powered by PageIndex.

WORKFLOW:
1. Call get_document_metadata() first to understand the document (page count, type).
2. Call get_document_structure() to see the hierarchical section index with summaries.
3. Reason about which sections are most relevant to the user's query.
4. Call get_page_content(pages="X-Y") with tight page ranges to read the actual text.
5. If the retrieved pages don't fully answer the query, fetch additional pages.
6. Compose your final answer based ONLY on the retrieved content.

STRICT RULES — THE FOUR CORNERS RULE:
- You MUST answer ONLY using content retrieved via tools. No outside legal knowledge.
- If the answer is not in any retrieved page, explicitly state:
  "The document does not contain this information."
- Always cite page numbers: "According to the document (Page X), ..."
- Never fabricate facts, dates, names, clauses, or legal terms.
- Before each tool call, output a brief sentence explaining WHY you are calling it.
- Be precise and professional — this is a legal context.
- Keep page fetches tight (2-5 pages). Never fetch the entire document."""


# ──────────────────────────────────────────────
# Tool Execution
# ──────────────────────────────────────────────
def execute_tool(document_id: str, tool_name: str, arguments: dict) -> str:
    """Execute a single tool call and return the result as a string."""
    try:
        if tool_name == "get_document_metadata":
            result = load_document_metadata(document_id)
            return json.dumps(result, indent=2)

        elif tool_name == "get_document_structure":
            result = load_document_structure(document_id)
            return json.dumps(result, indent=2)

        elif tool_name == "get_page_content":
            pages = arguments.get("pages", "1")
            return get_page_content(document_id, pages)

        else:
            return f"Unknown tool: {tool_name}"

    except FileNotFoundError as e:
        return f"Error: {str(e)}"
    except Exception as e:
        logger.error("Tool execution error (%s): %s", tool_name, e)
        return f"Error executing {tool_name}: {str(e)}"


# ──────────────────────────────────────────────
# Agentic Loop
# ──────────────────────────────────────────────
def _is_retryable(error: BaseException) -> bool:
    """Only retry on transient errors (5xx, network), NOT on 400 Bad Request."""
    if isinstance(error, BadRequestError):
        return False
    return True


@retry(
    stop=stop_after_attempt(2),
    wait=wait_exponential(multiplier=1, min=2, max=8),
    retry=retry_if_exception(_is_retryable),
)
def _call_groq(messages: list[dict], tools: list[dict]) -> Any:
    """Single Groq API call with retry on transient failures only."""
    client = get_groq_client()
    return client.chat.completions.create(
        model=settings.GROQ_MODEL,
        messages=messages,
        tools=tools,
        tool_choice="auto",
        temperature=0,
        max_tokens=2048,
    )


def run_agent(
    document_id: str,
    query: str,
    conversation_history: list[dict] | None = None,
) -> tuple[str, list[str], list[AgentToolCall]]:
    """
    Run the agentic document QA loop.

    The LLM autonomously decides which tools to call. It loops until
    it produces a final text answer or hits the max iteration limit.

    Args:
        document_id: ID of the uploaded document
        query: User's natural language question
        conversation_history: Previous conversation turns for multi-turn memory

    Returns:
        (answer, cited_pages, tool_calls_log)
    """
    # Build initial message list
    messages: list[dict] = [{"role": "system", "content": AGENT_SYSTEM_PROMPT}]

    # Add conversation history for multi-turn memory
    if conversation_history:
        for turn in conversation_history:
            role = turn.get("role", "user")
            content = turn.get("content", "")
            if role in ("user", "assistant") and content:
                messages.append({"role": role, "content": content})

    # Add the current query
    messages.append({"role": "user", "content": query})

    tool_calls_log: list[AgentToolCall] = []
    cited_pages: set[str] = set()

    for iteration in range(settings.AGENT_MAX_ITERATIONS):
        logger.info("[Agent] Iteration %d — calling Groq...", iteration + 1)

        try:
            response = _call_groq(messages, TOOL_DEFINITIONS)
        except BadRequestError as e:
            logger.error("[Agent] Groq 400 Bad Request: %s", e.message)
            return (
                f"The language model rejected the request: {e.message}",
                sorted(cited_pages),
                tool_calls_log,
            )
        except Exception as e:
            logger.error("[Agent] Groq API error: %s", e)
            return (
                f"I encountered an error communicating with the language model: {str(e)}",
                sorted(cited_pages),
                tool_calls_log,
            )

        choice = response.choices[0]
        message = choice.message

        # ── Case 1: LLM wants to call tools ──
        if message.tool_calls:
            # Manually construct a clean assistant message dict.
            # message.model_dump() includes SDK-internal fields that Groq rejects.
            assistant_msg = {
                "role": "assistant",
                "content": message.content or "",
                "tool_calls": [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {
                            "name": tc.function.name,
                            "arguments": tc.function.arguments or "{}",
                        },
                    }
                    for tc in message.tool_calls
                ],
            }
            messages.append(assistant_msg)

            for tool_call in message.tool_calls:
                fn_name = tool_call.function.name
                fn_args_str = tool_call.function.arguments or "{}"

                try:
                    fn_args = json.loads(fn_args_str)
                except json.JSONDecodeError:
                    fn_args = {}

                # Groq returns "null" for no-arg tools → json.loads gives None
                if not isinstance(fn_args, dict):
                    fn_args = {}

                logger.info("[Agent]   Tool call: %s(%s)", fn_name, fn_args)

                # Execute the tool
                result = execute_tool(document_id, fn_name, fn_args)

                # Track pages fetched for citations
                if fn_name == "get_page_content" and "pages" in fn_args:
                    from core.page_index import parse_page_ranges
                    try:
                        fetched = parse_page_ranges(fn_args["pages"])
                        for p in fetched:
                            cited_pages.add(str(p))
                    except ValueError:
                        pass

                # Log the tool call for the UI
                tool_calls_log.append(
                    AgentToolCall(
                        tool_name=fn_name,
                        arguments=fn_args,
                        result_preview=result[:200] + "..." if len(result) > 200 else result,
                    )
                )

                # Feed tool result back into the conversation
                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "content": result,
                    }
                )

            # Continue the loop — the LLM may want to call more tools
            continue

        # ── Case 2: LLM produced a final text answer (no tool calls) ──
        if message.content:
            final_answer = message.content.strip()
            logger.info(
                "[Agent] Final answer produced after %d iterations, %d tool calls.",
                iteration + 1,
                len(tool_calls_log),
            )
            return final_answer, sorted(cited_pages), tool_calls_log

        # ── Case 3: Empty response (shouldn't happen) ──
        logger.warning("[Agent] Empty response at iteration %d", iteration + 1)
        break

    # Exhausted max iterations
    logger.warning("[Agent] Reached max iterations (%d)", settings.AGENT_MAX_ITERATIONS)
    return (
        "I was unable to fully answer your question within the processing limit. "
        "Please try rephrasing or asking a more specific question.",
        sorted(cited_pages),
        tool_calls_log,
    )
