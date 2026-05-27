"""
main.py — FastAPI Application for Agentic Legal Document Chatbot

Endpoints:
  POST /upload           — Upload a PDF, extract text, build hierarchical tree index
  POST /chat             — Agentic QA loop (LLM decides which tools to call)
  GET  /document/{id}    — Document metadata (page count, status, filename)
"""

import os
import uuid
import asyncio
import logging

from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from core.models import ChatRequest, ChatResponse, UploadResponse, DocumentMetadata
from core.page_index import build_index, load_document_metadata
from core.agent import run_agent
from core.config import settings

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

MAX_UPLOAD_SIZE = 20 * 1024 * 1024  # 20 MB

app = FastAPI(
    title="Juris AI — Agentic Legal Document Intelligence",
    description="Agentic Vectorless RAG powered by PageIndex + Groq (Llama 3.3 70B)",
    version="2.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ──────────────────────────────────────────────
# Startup Validation
# ──────────────────────────────────────────────
@app.on_event("startup")
async def validate_config():
    if settings.GROQ_API_KEY in ("your-groq-api-key-here", ""):
        logger.error("GROQ_API_KEY is not configured! Set it in your .env file.")
        raise RuntimeError("GROQ_API_KEY is not configured. Set it in your .env file.")
    logger.info("Juris AI started. Model: %s", settings.GROQ_MODEL)


# ──────────────────────────────────────────────
# POST /upload
# ──────────────────────────────────────────────
@app.post("/upload", response_model=UploadResponse)
async def upload_document(file: UploadFile = File(...)):
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are supported.")

    content = await file.read()
    if len(content) > MAX_UPLOAD_SIZE:
        raise HTTPException(status_code=413, detail="File too large. Maximum upload size is 20 MB.")

    doc_id = str(uuid.uuid4())
    file_path = os.path.join(settings.UPLOAD_DIR, f"{doc_id}.pdf")

    with open(file_path, "wb") as f:
        f.write(content)

    try:
        page_texts, tree = await asyncio.to_thread(
            build_index, doc_id, file_path, file.filename
        )
        logger.info(
            "Document %s uploaded: %d pages, %d tree nodes",
            doc_id, len(page_texts), len(tree),
        )
        return UploadResponse(
            document_id=doc_id,
            message="Document uploaded and hierarchical PageIndex built successfully.",
            total_pages=len(page_texts),
        )
    except Exception as e:
        logger.error("Failed to process document %s: %s", doc_id, e)
        raise HTTPException(status_code=500, detail=f"Failed to process document: {str(e)}")


# ──────────────────────────────────────────────
# POST /chat  (Agentic Loop)
# ──────────────────────────────────────────────
@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    try:
        answer, cited_pages, tool_calls_log = await asyncio.to_thread(
            run_agent,
            request.document_id,
            request.query,
            request.conversation_history,
        )

        logger.info(
            "Chat for doc %s: %d tool calls, pages cited: %s",
            request.document_id, len(tool_calls_log), cited_pages,
        )

        return ChatResponse(
            answer=answer,
            cited_pages=cited_pages,
            tool_calls=[tc.model_dump() for tc in tool_calls_log],
            status="success",
        )

    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Document not found. Please upload it first.")
    except Exception as e:
        logger.error("Chat error for doc %s: %s", request.document_id, e)
        raise HTTPException(status_code=500, detail=f"Failed to answer query: {str(e)}")


# ──────────────────────────────────────────────
# GET /document/{doc_id}
# ──────────────────────────────────────────────
@app.get("/document/{doc_id}", response_model=DocumentMetadata)
async def get_document(doc_id: str):
    try:
        meta = await asyncio.to_thread(load_document_metadata, doc_id)
        return DocumentMetadata(**meta)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Document not found.")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
