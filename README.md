# Juris AI - Vectorless Legal RAG with PageIndex

Juris AI is a legal document question-answering application built with a vectorless RAG approach using PageIndex. It extracts text from uploaded PDF legal documents, builds a lightweight page-level index, retrieves the most relevant pages for a user query, and generates grounded answers with page citations.

## Features

- Upload and process PDF legal documents
- Extract page-level text using PyMuPDF
- Build a vectorless PageIndex without embeddings or a vector database
- Route user questions to the most relevant document pages
- Generate legal answers using Groq-hosted LLMs
- Cite the pages used to answer each query
- React frontend for document upload and chat
- FastAPI backend with PDF upload and chat endpoints

## Tech Stack

### Backend

- Python
- FastAPI
- PyMuPDF
- Groq API
- Pydantic

### Frontend

- React
- Vite
- Axios
- Lucide React

## Project Structure

```text
page_index/
├── core/
│   ├── config.py
│   ├── models.py
│   └── page_index.py
├── frontend/
│   ├── public/
│   ├── src/
│   ├── package.json
│   └── vite.config.js
├── uploads/
├── main.py
├── requirements.txt
├── test_bot.py
└── README.md
```

## How It Works

1. A user uploads a PDF legal document.
2. The backend extracts text from each page using PyMuPDF.
3. A PageIndex is generated from page-level text previews.
4. When the user asks a question, the router identifies the most relevant pages from the PageIndex.
5. The answer generator uses only the retrieved pages to produce a response.
6. The response includes page citations so the answer stays grounded in the source document.

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
```

Run the backend:

```powershell
python main.py
```

The backend will run at:

```text
http://localhost:8000
```

## Frontend Setup

Move into the frontend directory:

```powershell
cd frontend
```

Install dependencies:

```powershell
npm install
```

Run the development server:

```powershell
npm run dev
```

The frontend will run at:

```text
http://localhost:5173
```

## API Endpoints

### Upload Document

```http
POST /upload
```

Uploads a PDF document and builds its PageIndex.

### Chat with Document

```http
POST /chat
```

Sends a user query for a previously uploaded document.

Example request:

```json
{
  "document_id": "uploaded-document-id",
  "query": "What are the termination clauses in this agreement?"
}
```

## Environment Variables

| Variable | Description |
| --- | --- |
| `GROQ_API_KEY` | API key used to access Groq models |
| `GROQ_MODEL` | Model used for page routing and answer generation |
| `UPLOAD_DIR` | Directory where uploaded PDFs and generated indexes are stored |

## Notes

- Do not commit `.env` files or API keys.
- Do not commit uploaded legal documents unless they are public sample files.
- This project is designed for document-grounded assistance and should not be treated as legal advice.

