# Juris AI - Agentic Vectorless Legal RAG with PageIndex

Juris AI is a legal document question-answering application built with a custom
PageIndex-style, vectorless RAG backend. Uploaded PDFs are extracted page by
page, organized into an LLM-generated hierarchical document tree, and queried
through an agentic tool-calling workflow that produces document-grounded
answers with page citations.

The project does not use embeddings or a vector database. Instead, it uses a
semantic tree index to help an LLM agent decide which source pages to read in
full before answering a question.

## Backend Features

- Upload and validate PDF legal documents
- Extract page-level text using PyMuPDF
- Build a hierarchical semantic tree index from page previews
- Persist original PDFs, extracted page text, tree indexes, and metadata
- Run an agentic question-answering loop through `core/agent.py`
- Expose tools for metadata lookup, structure navigation, and page retrieval
- Support multi-turn questions through conversation history
- Return cited pages and tool-call traces with each response
- Apply grounded-answer rules for legal document analysis
- Retry transient model failures and enforce agent/page-fetch limits

## Backend Tech Stack

| Technology | Purpose |
| --- | --- |
| Python | Backend application language |
| FastAPI | REST API endpoints and request handling |
| Uvicorn | ASGI application server |
| Pydantic | Request and response validation |
| pydantic-settings | Environment configuration management |
| PyMuPDF | PDF page text extraction |
| Groq API | Hosted LLM inference and function/tool calling |
| Tenacity | Retry handling for transient LLM failures |
| python-multipart | PDF upload processing |
| JSON file persistence | Document text, tree index, and metadata storage |

## Backend Architecture

The backend is a modular monolith implementing an agentic, vectorless RAG
architecture:

```text
PDF Upload
  -> FastAPI validation and UUID assignment
  -> PyMuPDF page-by-page extraction
  -> Groq-generated hierarchical tree index
  -> JSON metadata/index persistence

User Query
  -> FastAPI chat endpoint
  -> Agentic Groq tool-calling loop
  -> Inspect metadata and document structure
  -> Retrieve selected source pages
  -> Grounded answer with page citations
```

### Why Vectorless RAG?

Traditional RAG commonly creates embeddings and queries a vector database. This
implementation instead builds a semantic tree similar to a smart table of
contents. For structured legal documents, the agent can inspect relevant
sections first and fetch only the pages needed to answer the query.

## Project Structure

```text
page_index/
|-- core/
|   |-- __init__.py
|   |-- agent.py          # Agent tools, prompts, and tool-calling loop
|   |-- config.py         # Environment settings and agent limits
|   |-- models.py         # Pydantic API and tool-trace models
|   `-- page_index.py     # PDF extraction, tree indexing, and retrieval tools
|-- uploads/              # Runtime PDF and JSON artifacts (gitignored)
|-- main.py               # FastAPI application and endpoints
|-- requirements.txt
|-- test_bot.py
`-- README.md
```

## How It Works

### 1. Document Upload and Indexing

1. A PDF is submitted to `POST /upload`.
2. The backend checks the `.pdf` extension and enforces a 20 MB upload limit.
3. A UUID is created as the document identifier and the PDF is written to the
   configured upload directory.
4. PyMuPDF extracts plain text from each page and stores it using page-number
   keys.
5. The backend sends condensed page previews to the configured Groq model.
6. The model returns a hierarchical JSON tree containing section titles,
   summaries, page ranges, and nested child sections.
7. The page text, tree structure, and document metadata are persisted as JSON.
8. If semantic tree creation fails, the backend falls back to a flat per-page
   index so the document remains available.

Generated files for a document:

```text
uploads/{document_id}.pdf
uploads/{document_id}.json
uploads/{document_id}_tree.json
uploads/{document_id}_meta.json
```

### 2. Agentic Document Chat

`core/agent.py` replaces a fixed router/generator pipeline with an autonomous
tool-calling loop:

1. A question is submitted to `POST /chat` with a document ID and optional
   conversation history.
2. The agent sends the query, history, system grounding rules, and available
   tool definitions to Groq.
3. The model chooses which retrieval tool to call.
4. Tool results are returned to the model as additional context.
5. The model may retrieve more pages or produce a final answer.
6. The final API response includes the answer, pages retrieved for citations,
   and a tool-call trace.

### Agent Tools

| Tool | Responsibility |
| --- | --- |
| `get_document_metadata` | Returns filename, page count, status, and indexing timestamp |
| `get_document_structure` | Returns the hierarchical tree index for section-level navigation |
| `get_page_content` | Returns full text for requested page ranges such as `3-5,8` |

### Grounding Rules

The agent is instructed to follow a four-corners rule:

- Answer only from document content retrieved through tools.
- Avoid adding outside legal knowledge or unsupported assumptions.
- State when the requested information is not contained in the document.
- Cite relevant page numbers in the final answer.

## API Endpoints

### Upload Document

```http
POST /upload
```

Uploads a PDF and builds its hierarchical PageIndex-style index.

Response example:

```json
{
  "document_id": "uploaded-document-id",
  "message": "Document uploaded and hierarchical PageIndex built successfully.",
  "total_pages": 12
}
```

### Chat With Document

```http
POST /chat
```

Request example:

```json
{
  "document_id": "uploaded-document-id",
  "query": "What are the termination clauses in this agreement?",
  "conversation_history": []
}
```

Response shape:

```json
{
  "answer": "According to the document (Page 8), ...",
  "cited_pages": ["8"],
  "tool_calls": [
    {
      "tool_name": "get_page_content",
      "arguments": {
        "pages": "8"
      },
      "result_preview": "--- Page 8 --- ..."
    }
  ],
  "status": "success"
}
```

### Get Document Metadata

```http
GET /document/{doc_id}
```

Response example:

```json
{
  "document_id": "uploaded-document-id",
  "filename": "agreement.pdf",
  "total_pages": 12,
  "status": "indexed",
  "indexed_at": "2026-05-26T10:34:00+00:00"
}
```

## Backend Setup

Create and activate a virtual environment:

```powershell
python -m venv venv
.\venv\Scripts\activate
```

Install dependencies:

```powershell
pip install -r requirements.txt
```

Create a `.env` file in the project root:

```env
GROQ_API_KEY=your-groq-api-key
GROQ_MODEL=llama-3.3-70b-versatile
UPLOAD_DIR=./uploads
AGENT_MAX_ITERATIONS=10
AGENT_MAX_PAGE_FETCH=8
```

Run the API:

```powershell
python main.py
```

The backend runs at:

```text
http://localhost:8000
```

Interactive API documentation is available at:

```text
http://localhost:8000/docs
```

## Configuration

| Variable | Description | Default |
| --- | --- | --- |
| `GROQ_API_KEY` | API key used for Groq model calls | Required |
| `GROQ_MODEL` | Model used for tree indexing and agent reasoning | `llama-3.3-70b-versatile` |
| `UPLOAD_DIR` | Directory for document and JSON artifacts | `./uploads` |
| `AGENT_MAX_ITERATIONS` | Maximum tool-calling iterations per question | `10` |
| `AGENT_MAX_PAGE_FETCH` | Maximum pages returned in one page-content call | `8` |

## Reliability and Safety

- The application validates that a Groq API key is configured at startup.
- PDF uploads are limited to 20 MB.
- Tree index generation retries transient failures and falls back to a flat
  page index when required.
- Agent model calls retry transient failures but do not repeatedly retry invalid
  requests.
- Tool loops and retrieved page counts are limited through configuration.
- `.env` and `uploads/` are ignored by Git to avoid publishing secrets and
  uploaded documents.

## Current Limitations

- Storage uses local files rather than a database or object store.
- Scanned PDFs without extractable text require an OCR enhancement.
- Conversation history is passed with each request rather than stored server-side.
- The existing test file is minimal and should be expanded with endpoint and
  agent-tool unit tests.

## Disclaimer

This project provides document-grounded assistance and is not legal advice.
