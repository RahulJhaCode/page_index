import os
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    # Groq Cloud settings
    GROQ_API_KEY: str = "your-groq-api-key-here"

    # Groq model to use for routing & generation
    # Best free model for legal reasoning — Llama 3.3 70B on Groq
    GROQ_MODEL: str = "llama-3.3-70b-versatile"

    # Upload directory for PDF files and index files
    UPLOAD_DIR: str = "./uploads"

    class Config:
        env_file = ".env"

settings = Settings()

# Ensure uploads directory exists
os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
