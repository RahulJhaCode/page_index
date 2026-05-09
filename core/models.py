from pydantic import BaseModel
from typing import List, Optional

class ChatRequest(BaseModel):
    document_id: str
    query: str

class ChatResponse(BaseModel):
    answer: str
    cited_pages: List[str]
    status: str

class UploadResponse(BaseModel):
    document_id: str
    message: str
    total_pages: int
