import os
import uuid
import asyncio
import logging

from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from core.models import ChatRequest, ChatResponse, UploadResponse
from core.page_index import build_index, load_document_data, retrieve_pages, generate_answer
from core.config import settings

logger = logging.getLogger(__name__)

MAX_UPLOAD_SIZE = 20 * 1024 * 1024  # 20 MB

app = FastAPI(title="Legal Document Chatbot", description="PageIndex vectorless document querying")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],  # Restrict to frontend dev server
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
@app.post("/upload", response_model=UploadResponse)
async def upload_document(file: UploadFile = File(...)):
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are supported.")

    # Read and enforce size limit
    content = await file.read()
    if len(content) > MAX_UPLOAD_SIZE:
        raise HTTPException(status_code=413, detail="File too large. Maximum upload size is 20 MB.")

    doc_id = str(uuid.uuid4())
    file_path = os.path.join(settings.UPLOAD_DIR, f"{doc_id}.pdf")

    # Save uploaded file
    with open(file_path, "wb") as f:
        f.write(content)

    try:
        page_texts, index_str = await asyncio.to_thread(build_index, doc_id, file_path)
        logger.info("Document %s uploaded successfully (%d pages)", doc_id, len(page_texts))
        return UploadResponse(
            document_id=doc_id,
            message="Document uploaded and PageIndex built successfully.",
            total_pages=len(page_texts)
        )
    except Exception as e:
        logger.error("Failed to process document %s: %s", doc_id, e)
        raise HTTPException(status_code=500, detail=f"Failed to process document: {str(e)}")

@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    try:
        # 1. Load document text and the PageIndex
        page_texts, index_str = await asyncio.to_thread(load_document_data, request.document_id)

        # 2. Router Step: Which pages might answer this question?
        relevant_pages = await asyncio.to_thread(retrieve_pages, request.query, index_str)

        # 3. Generator Step: Read the relevant pages and provide an exact answer
        final_answer, pages_used = await asyncio.to_thread(
            generate_answer, request.query, page_texts, relevant_pages
        )

        logger.info("Chat query answered for doc %s, pages used: %s", request.document_id, pages_used)
        return ChatResponse(
            answer=final_answer,
            cited_pages=pages_used,
            status="success"
        )

    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Document ID not found. Has it been uploaded?")
    except Exception as e:
        logger.error("Chat error for doc %s: %s", request.document_id, e)
        raise HTTPException(status_code=500, detail=f"Failed to answer query: {str(e)}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
