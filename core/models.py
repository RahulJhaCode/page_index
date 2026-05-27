from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any


class AgentToolCall(BaseModel):
    """Record of a single tool call made by the agent during reasoning."""
    tool_name: str
    arguments: Dict[str, Any] = {}
    result_preview: str = ""  # First 200 chars of the tool result


class ChatRequest(BaseModel):
    document_id: str
    query: str
    conversation_history: List[Dict[str, str]] = Field(
        default_factory=list,
        description="Previous turns: [{role: 'user'|'assistant', content: '...'}]"
    )


class ChatResponse(BaseModel):
    answer: str
    cited_pages: List[str]
    tool_calls: List[AgentToolCall] = []  # Trace of agent reasoning steps
    status: str


class UploadResponse(BaseModel):
    document_id: str
    message: str
    total_pages: int


class DocumentMetadata(BaseModel):
    document_id: str
    filename: str
    total_pages: int
    status: str
    indexed_at: str
