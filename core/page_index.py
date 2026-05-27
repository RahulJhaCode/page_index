"""
core/page_index.py — Vectorless PageIndex with Hierarchical Tree Indexing

Responsibilities:
  1. Extract text page-by-page from PDFs using PyMuPDF
  2. Build an LLM-generated hierarchical tree index (semantic TOC)
  3. Persist page texts, tree structure, and metadata to disk
  4. Provide tool-callable functions for the agent:
     - get_document_metadata()
     - get_document_structure()
     - get_page_content(pages)
"""

import os
import json
from datetime import datetime, timezone

import pymupdf
from groq import Groq
from tenacity import retry, stop_after_attempt, wait_exponential

from core.config import settings


# ──────────────────────────────────────────────
# Groq Client
# ──────────────────────────────────────────────
_groq_client: Groq | None = None


def get_groq_client() -> Groq:
    global _groq_client
    if _groq_client is None:
        _groq_client = Groq(api_key=settings.GROQ_API_KEY)
    return _groq_client


# ──────────────────────────────────────────────
# PDF Text Extraction
# ──────────────────────────────────────────────
def extract_text_per_page(pdf_path: str) -> dict:
    """
    Extracts text from each page of a PDF using PyMuPDF.
    Returns: {"1": "page 1 text", "2": "page 2 text", ...}
    """
    page_texts = {}
    doc = pymupdf.open(pdf_path)
    for page_num in range(len(doc)):
        page = doc.load_page(page_num)
        text = page.get_text("text").strip()
        page_texts[str(page_num + 1)] = text if text else "[No parseable text on this page]"
    doc.close()
    return page_texts


# ──────────────────────────────────────────────
# Hierarchical Tree Index Generation
# ──────────────────────────────────────────────
@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
def build_tree_structure(page_texts: dict) -> list[dict]:
    """
    Uses Groq (Llama 3.3 70B) to generate a hierarchical tree index
    from the extracted page texts. This is the 'smart Table of Contents'
    that the agent will reason over — far superior to flat 300-char previews.

    Returns a list of tree nodes:
    [
      {
        "title": "Section Name",
        "summary": "1-2 sentence description of what this section covers",
        "start_page": 1,
        "end_page": 3,
        "children": [ ... nested nodes ... ]
      }
    ]
    """
    client = get_groq_client()

    # Build a condensed representation for the LLM (first 200 chars per page)
    page_previews = []
    for page_num, text in page_texts.items():
        preview = text[:200].replace("\n", " ").strip()
        page_previews.append(f"Page {page_num}: {preview}")

    previews_str = "\n".join(page_previews)

    system_prompt = """You are a document structure analyst. Given page previews of a document,
generate a hierarchical tree structure (like a smart Table of Contents).

RULES:
- Each node must have: "title", "summary" (1-2 sentences), "start_page" (int), "end_page" (int), "children" (array)
- Group related pages into logical sections
- Use nested children for sub-sections where appropriate
- The summary should describe the LEGAL CONTENT of the section, not just repeat headings
- Return ONLY a valid JSON array of nodes. No markdown, no explanation."""

    user_prompt = f"""Generate a hierarchical tree structure for this document:

{previews_str}

Return a JSON array of tree nodes."""

    response = client.chat.completions.create(
        model=settings.GROQ_MODEL,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0,
        max_tokens=2048,
    )

    content = response.choices[0].message.content.strip()

    # Extract JSON array from response
    if "[" in content:
        start = content.find("[")
        end = content.rfind("]") + 1
        tree = json.loads(content[start:end])
        return tree

    # Fallback: flat structure if LLM doesn't produce a tree
    return [
        {
            "title": f"Page {p}",
            "summary": page_texts[p][:150],
            "start_page": int(p),
            "end_page": int(p),
            "children": [],
        }
        for p in page_texts
    ]


# ──────────────────────────────────────────────
# Build Index (called during upload)
# ──────────────────────────────────────────────
def build_index(document_id: str, pdf_path: str, filename: str = "") -> tuple[dict, list[dict]]:
    """
    Full indexing pipeline:
      1. Extract text per page (PyMuPDF)
      2. Generate hierarchical tree index (Groq LLM)
      3. Save page texts, tree structure, and metadata to disk

    Returns: (page_texts, tree_structure)
    """
    print(f"[PageIndex] Extracting pages from: {pdf_path}")
    page_texts = extract_text_per_page(pdf_path)
    total_pages = len(page_texts)
    print(f"[PageIndex] Found {total_pages} pages.")

    # Generate hierarchical tree
    print("[PageIndex] Building hierarchical tree index via LLM...")
    try:
        tree_structure = build_tree_structure(page_texts)
        print(f"[PageIndex] Tree built with {len(tree_structure)} top-level nodes.")
    except Exception as e:
        print(f"[PageIndex] Tree generation failed, using flat fallback: {e}")
        tree_structure = [
            {
                "title": f"Page {p}",
                "summary": page_texts[p][:150],
                "start_page": int(p),
                "end_page": int(p),
                "children": [],
            }
            for p in page_texts
        ]

    # Persist to disk
    texts_path = os.path.join(settings.UPLOAD_DIR, f"{document_id}.json")
    tree_path = os.path.join(settings.UPLOAD_DIR, f"{document_id}_tree.json")
    meta_path = os.path.join(settings.UPLOAD_DIR, f"{document_id}_meta.json")

    with open(texts_path, "w", encoding="utf-8") as f:
        json.dump(page_texts, f)

    with open(tree_path, "w", encoding="utf-8") as f:
        json.dump(tree_structure, f, indent=2)

    metadata = {
        "document_id": document_id,
        "filename": filename or os.path.basename(pdf_path),
        "total_pages": total_pages,
        "status": "indexed",
        "indexed_at": datetime.now(timezone.utc).isoformat(),
    }
    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump(metadata, f, indent=2)

    return page_texts, tree_structure


# ──────────────────────────────────────────────
# Tool Functions (called by the Agent)
# ──────────────────────────────────────────────
def load_document_metadata(document_id: str) -> dict:
    """Tool: get_document_metadata — returns doc info (page count, status, filename)."""
    meta_path = os.path.join(settings.UPLOAD_DIR, f"{document_id}_meta.json")
    if not os.path.exists(meta_path):
        raise FileNotFoundError(f"Document '{document_id}' not found.")
    with open(meta_path, "r", encoding="utf-8") as f:
        return json.load(f)


def load_document_structure(document_id: str) -> list[dict]:
    """Tool: get_document_structure — returns the hierarchical tree index."""
    tree_path = os.path.join(settings.UPLOAD_DIR, f"{document_id}_tree.json")
    if not os.path.exists(tree_path):
        raise FileNotFoundError(f"Document structure for '{document_id}' not found.")
    with open(tree_path, "r", encoding="utf-8") as f:
        return json.load(f)


def load_page_texts(document_id: str) -> dict:
    """Load all page texts from disk."""
    texts_path = os.path.join(settings.UPLOAD_DIR, f"{document_id}.json")
    if not os.path.exists(texts_path):
        raise FileNotFoundError(f"Document texts for '{document_id}' not found.")
    with open(texts_path, "r", encoding="utf-8") as f:
        return json.load(f)


def parse_page_ranges(pages_str: str) -> list[int]:
    """
    Parse page range strings like '3-5,8,12-14' into a list of integers.
    Returns: [3, 4, 5, 8, 12, 13, 14]
    """
    result = []
    for part in pages_str.split(","):
        part = part.strip()
        if "-" in part:
            start_str, end_str = part.split("-", 1)
            start, end = int(start_str.strip()), int(end_str.strip())
            result.extend(range(start, end + 1))
        else:
            result.append(int(part))
    return sorted(set(result))


def get_page_content(document_id: str, pages: str) -> str:
    """
    Tool: get_page_content — fetches full text of specific pages.
    Accepts ranges like '3-5,8'. Enforces AGENT_MAX_PAGE_FETCH limit.
    """
    page_texts = load_page_texts(document_id)
    page_nums = parse_page_ranges(pages)

    # Enforce safety limit
    if len(page_nums) > settings.AGENT_MAX_PAGE_FETCH:
        page_nums = page_nums[: settings.AGENT_MAX_PAGE_FETCH]

    result_parts = []
    for p in page_nums:
        key = str(p)
        if key in page_texts:
            result_parts.append(f"--- Page {p} ---\n{page_texts[key]}")
        else:
            result_parts.append(f"--- Page {p} ---\n[Page does not exist]")

    return "\n\n".join(result_parts)
