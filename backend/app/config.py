from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field, model_validator
import os
from pathlib import Path

# Base backend directory
BASE_DIR = Path(__file__).resolve().parent.parent

class Settings(BaseSettings):
    # App Settings
    APP_NAME: str = "Opportunity Intelligence AI"
    APP_ENV: str = "development"
    DEBUG: bool = True
    PORT: int = 8000
    HOST: str = "0.0.0.0"
    SECRET_KEY: str = "super_secret_development_key_not_for_production_32chars"
    
    # LLM Settings
    GROQ_API_KEY: str = Field(default="", description="Groq Cloud API Key")
    GROQ_MODEL: str = "llama-3.3-70b-versatile"
    
    # RAG Settings
    CHROMA_PERSIST_DIRECTORY: str = str(BASE_DIR / "data" / "chromadb")
    CHROMA_COLLECTION_NAME: str = "kenya_opportunities"
    EMBEDDING_MODEL_NAME: str = "sentence-transformers/all-MiniLM-L6-v2"
    RAW_DATA_DIRECTORY: str = str(BASE_DIR / "data" / "raw_opportunities")
    
    # Relational DB Settings
    DATABASE_URL: str = f"sqlite:///{BASE_DIR}/data/app.db"
    
    # CORS
    ALLOWED_ORIGINS: str = "http://localhost:5173,http://127.0.0.1:5173"
    
    @model_validator(mode="after")
    def resolve_paths(self):
        # Ensure Chroma path is absolute anchored at BASE_DIR
        chroma_path = Path(self.CHROMA_PERSIST_DIRECTORY)
        if not chroma_path.is_absolute():
            self.CHROMA_PERSIST_DIRECTORY = str((BASE_DIR / chroma_path).resolve())
        
        # Ensure SQLite path is absolute anchored at BASE_DIR
        if self.DATABASE_URL.startswith("sqlite:///") and not self.DATABASE_URL.startswith("sqlite:////"):
            rel_part = self.DATABASE_URL.replace("sqlite:///", "")
            if rel_part.startswith("./"):
                rel_part = rel_part[2:]
            self.DATABASE_URL = f"sqlite:///{BASE_DIR / rel_part}"

        return self

    model_config = SettingsConfigDict(
        env_file=str(BASE_DIR / ".env"),
        env_file_encoding="utf-8",
        extra="ignore"
    )

settings = Settings()
