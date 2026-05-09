import os
import json
import pymupdf
from groq import Groq
from core.config import settings


# ──────────────────────────────────────────────
# Groq Client (singleton — reused across calls)
# ──────────────────────────────────────────────
def get_groq_client() -> Groq:
    return Groq(api_key=settings.GROQ_API_KEY)


# ──────────────────────────────────────────────
# Step 0: PDF Text Extraction (via PyMuPDF)
# ──────────────────────────────────────────────
def extract_text_per_page(pdf_path: str) -> dict:
    """
    Extracts text from each page of a PDF.
    Returns: { "1": "page 1 text", "2": "page 2 text", ... }
    """
    page_texts = {}
    doc = pymupdf.open(pdf_path)
    for page_num in range(len(doc)):
        page = doc.load_page(page_num)
        text = page.get_text("text").strip()
        page_texts[str(page_num + 1)] = text if text else "No parseable text on this page."
    doc.close()
    return page_texts


# ──────────────────────────────────────────────
# Step 1: Build PageIndex (vectorless)
# ──────────────────────────────────────────────
def build_index(document_id: str, pdf_path: str) -> tuple[dict, str]:
    """
    Vectorless PageIndex strategy:
      - Extract raw text page-by-page using PyMuPDF
      - Build a lightweight plain-text structural index (first 300 chars per page)
      - Save both to disk for later retrieval
    """
    print(f"[PageIndex] Extracting pages from: {pdf_path}")
    page_texts = extract_text_per_page(pdf_path)
    total_pages = len(page_texts)
    print(f"[PageIndex] Found {total_pages} pages.")

    # Build the page index string (Table of Contents snapshot)
    index_lines = []
    for page_num, text in page_texts.items():
        preview = text[:300].replace("\n", " ").strip()
        index_lines.append(f"Page {page_num}: {preview}...")

    index_str = "\n".join(index_lines)

    # Persist texts and index to disk
    doc_path = os.path.join(settings.UPLOAD_DIR, f"{document_id}.json")
    index_path = os.path.join(settings.UPLOAD_DIR, f"{document_id}_index.txt")

    with open(doc_path, "w", encoding="utf-8") as f:
        json.dump(page_texts, f)

    with open(index_path, "w", encoding="utf-8") as f:
        f.write(index_str)

    return page_texts, index_str


# ──────────────────────────────────────────────
# Step 2: Load from Disk
# ──────────────────────────────────────────────
def load_document_data(document_id: str) -> tuple[dict, str]:
    doc_path = os.path.join(settings.UPLOAD_DIR, f"{document_id}.json")
    index_path = os.path.join(settings.UPLOAD_DIR, f"{document_id}_index.txt")

    if not os.path.exists(doc_path) or not os.path.exists(index_path):
        raise FileNotFoundError(f"Document ID '{document_id}' not found. Please upload the document first.")

    with open(doc_path, "r", encoding="utf-8") as f:
        page_texts = json.load(f)

    with open(index_path, "r", encoding="utf-8") as f:
        index_str = f.read()

    return page_texts, index_str


# ──────────────────────────────────────────────
# Step 3: Router — which pages are relevant?
# ──────────────────────────────────────────────
def retrieve_pages(query: str, index_str: str) -> list[str]:
    """
    Groq (Llama 3.1 70B) reads the PageIndex and reasons about
    which page numbers are most likely to contain the answer.
    Returns a list of page number strings e.g. ["3", "7", "12"]
    """
    client = get_groq_client()

    system_prompt = """You are a legal document retrieval assistant using the PageIndex technique.
You are given a structural index of a document (a summary of each page).
Your task is to identify which page numbers are most likely to contain the answer to the user's query.

RULES:
- Return ONLY a raw JSON array of page number strings. Example: ["3", "7", "12"]
- Do NOT include any explanation, markdown, or extra text — ONLY the JSON array.
- If no pages are relevant, return an empty array: []
- Be precise. Prefer fewer, highly relevant pages over many loosely relevant ones."""

    user_prompt = f"""Document PageIndex:
{index_str}

User Query: {query}

Respond with a JSON array of the most relevant page numbers."""

    try:
        response = client.chat.completions.create(
            model=settings.GROQ_MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0,          # deterministic routing
            max_tokens=256,         # page list is small
        )
        content = response.choices[0].message.content.strip()

        # Safely extract JSON array from the response
        if "[" in content and "]" in content:
            start = content.find("[")
            end = content.rfind("]") + 1
            return json.loads(content[start:end])
        return []

    except Exception as e:
        print(f"[PageIndex] Router error: {e}")
        return []


# ──────────────────────────────────────────────
# Step 4: Generator — answer from exact pages
# ──────────────────────────────────────────────
def generate_answer(query: str, page_texts: dict, relevant_pages: list[str]) -> tuple[str, list[str]]:
    """
    Groq (Llama 3.1 70B) reads ONLY the content from the retrieved pages
    and generates a precise, citation-backed legal answer.
    Enforces the Four Corners Rule — no hallucination from outside the document.
    """
    if not relevant_pages:
        return "The document does not contain information relevant to your query.", []

    # Build context from only the retrieved pages
    context = ""
    valid_pages = []
    for page in relevant_pages:
        page_key = str(page)
        if page_key in page_texts:
            valid_pages.append(page_key)
            context += f"\n--- Page {page_key} ---\n{page_texts[page_key]}\n"

    if not context.strip():
        return "The document does not contain information relevant to your query.", []

    client = get_groq_client()

    system_prompt = """You are a highly accurate legal document assistant.

STRICT RULES — THE FOUR CORNERS RULE:
1. You MUST answer ONLY using the provided document context below.
2. Do NOT use any outside legal knowledge, case law, or assumptions.
3. If the answer is not explicitly present in the context, you MUST respond:
   "The document does not contain this information."
4. Always cite the exact page number where you found each piece of information.
   Example: "According to the document (Page 3), the termination clause states..."
5. Never fabricate facts, dates, names, or clauses.
6. Be precise and professional — this is a legal context."""

    user_prompt = f"""Document Context (Retrieved Pages Only):
{context}

User Query: {query}

Provide a precise, citation-backed answer based solely on the context above."""

    try:
        response = client.chat.completions.create(
            model=settings.GROQ_MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0,          # zero temperature for factual legal answers
            max_tokens=1024,
        )
        answer = response.choices[0].message.content.strip()
        return answer, valid_pages

    except Exception as e:
        print(f"[PageIndex] Generator error: {e}")
        return f"An error occurred while generating the answer: {str(e)}", []
