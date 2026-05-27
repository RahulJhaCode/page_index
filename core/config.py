import os
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Groq Cloud settings
    GROQ_API_KEY: str = "your-groq-api-key-here"

    # Groq model — Llama 3.3 70B on Groq (free, 128K context)
    GROQ_MODEL: str = "llama-3.3-70b-versatile"

    # Upload directory for PDF files, index files, and metadata
    UPLOAD_DIR: str = "./uploads"

    # ── Agent Configuration ──
    # Max iterations the agent can loop (tool calls) before forced stop
    AGENT_MAX_ITERATIONS: int = 10

    # Max pages the agent can fetch in a single get_page_content() call
    AGENT_MAX_PAGE_FETCH: int = 8

    class Config:
        env_file = ".env"


settings = Settings()

# Ensure uploads directory exists
os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
