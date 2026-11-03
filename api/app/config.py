from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field, model_validator
import os
from typing import Optional
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

class Settings(BaseSettings):
    APP_NAME: str = "Opportunity Intelligence AI"
    APP_ENV: str = "development"
    DEBUG: bool = True
    PORT: int = 8000
    HOST: str = "0.0.0.0"

    SECRET_KEY: str = "super_secret_development_key_not_for_production_32chars"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7
    ADMIN_REGISTRATION_SECRET: str = "kenya_admin_secret_key_2026"
    
    GROQ_API_KEY: str = Field(default="", description="Groq Cloud API Key")
    GROQ_MODEL: str = "llama-3.3-70b-versatile"
    
    CHROMA_PERSIST_DIRECTORY: str = str(BASE_DIR / "data" / "chromadb")
    CHROMA_COLLECTION_NAME: str = "kenya_opportunities"
    EMBEDDING_MODEL_NAME: str = "sentence-transformers/all-MiniLM-L6-v2"
    RAW_DATA_DIRECTORY: str = str(BASE_DIR / "data" / "raw_opportunities")
    
    DATABASE_URL: str = f"sqlite:///{BASE_DIR}/data/app.db"
    
    ALLOWED_ORIGINS: str = "http://localhost:5173,http://127.0.0.1:5173"
    RATE_LIMITING_ENABLED: bool = True
    UPSTASH_REDIS_REST_URL: Optional[str] = Field(default=None, description="Optional Upstash Redis REST URL for distributed serverless rate limiting")
    UPSTASH_REDIS_REST_TOKEN: Optional[str] = Field(default=None, description="Optional Upstash Redis REST Token for distributed serverless rate limiting")
    
    @model_validator(mode="after")
    def validate_production_secrets_and_paths(self):
        is_production = self.APP_ENV.lower() in ["production", "prod", "staging"]
        insecure_secret_keys = {
            "super_secret_development_key_not_for_production_32chars",
            "change_this_to_a_secure_random_key_in_production",
            "replace_with_a_secure_random_key_of_at_least_32_characters",
            "secret",
            "changeme",
            "admin",
            "123456"
        }
        insecure_admin_secrets = {
            "kenya_admin_secret_key_2026",
            "replace_with_a_secure_admin_registration_token_of_at_least_16_characters",
            "admin_secret",
            "secret",
            "admin"
        }

        if is_production:
            if not self.SECRET_KEY or self.SECRET_KEY in insecure_secret_keys:
                raise ValueError(
                    "CRITICAL SECURITY CONFIGURATION ERROR: SECRET_KEY must be set to a dedicated, cryptographically secure value in production. Development fallbacks are strictly prohibited."
                )
            if len(self.SECRET_KEY) < 32:
                raise ValueError(
                    "CRITICAL SECURITY CONFIGURATION ERROR: SECRET_KEY must be at least 32 characters in length for production environments."
                )

            if not self.ADMIN_REGISTRATION_SECRET or self.ADMIN_REGISTRATION_SECRET in insecure_admin_secrets:
                raise ValueError(
                    "CRITICAL SECURITY CONFIGURATION ERROR: ADMIN_REGISTRATION_SECRET must be set to a dedicated secure secret in production. Development fallbacks are strictly prohibited."
                )
            if len(self.ADMIN_REGISTRATION_SECRET) < 16:
                raise ValueError(
                    "CRITICAL SECURITY CONFIGURATION ERROR: ADMIN_REGISTRATION_SECRET must be at least 16 characters in length for production environments."
                )

            # Fail-closed production CORS origin enforcement
            cors_origins = [o.strip() for o in (self.ALLOWED_ORIGINS or "").split(",") if o.strip()]
            if not cors_origins:
                raise ValueError(
                    "CRITICAL SECURITY CONFIGURATION ERROR: ALLOWED_ORIGINS must be explicitly configured with trusted domains in production. Empty origins and localhost fallbacks are strictly prohibited."
                )
            if "*" in cors_origins:
                raise ValueError(
                    "CRITICAL SECURITY CONFIGURATION ERROR: Wildcard origin '*' is strictly prohibited in production when credentials are enabled."
                )

        chroma_path = Path(self.CHROMA_PERSIST_DIRECTORY)
        if not chroma_path.is_absolute():
            self.CHROMA_PERSIST_DIRECTORY = str((BASE_DIR / chroma_path).resolve())
        
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
