"""
Application configuration using Pydantic Settings.
All values loaded from environment variables / .env file.
"""
from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── Gemini API ───────────────────────────────────────────────────────
    GEMINI_API_KEY: str = ""
    GEMINI_LLM_MODEL: str = "gemini-2.5-flash"
    GEMINI_EMBED_MODEL: str = "text-embedding-004"

    # ── PostgreSQL ───────────────────────────────────────────────────────
    POSTGRES_USER: str = "ddcopilot"
    POSTGRES_PASSWORD: str = "changeme"
    POSTGRES_DB: str = "ddcopilot"
    POSTGRES_HOST: str = "postgres"
    POSTGRES_PORT: int = 5432

    DATABASE_URL: str | None = None
    DATABASE_URL_SYNC: str | None = None


    # ── Qdrant ───────────────────────────────────────────────────────────
    QDRANT_URL: str | None = None
    QDRANT_API_KEY: str | None = None
    QDRANT_HOST: str = "qdrant"
    QDRANT_PORT: int = 6333
    QDRANT_COLLECTION: str = "due_diligence_chunks"

    # ── Redis ────────────────────────────────────────────────────────────
    REDIS_URL: str = "redis://redis:6379/0"

    # ── MinIO ────────────────────────────────────────────────────────────
    MINIO_ENDPOINT: str = "minio:9000"
    MINIO_ACCESS_KEY: str = "minioadmin"
    MINIO_SECRET_KEY: str = "minioadmin"
    MINIO_BUCKET_NAME: str = "forinvest"
    MINIO_SECURE: bool = False

    def model_post_init(self, __context) -> None:
        # Keep a raw copy of DATABASE_URL before we modify it for asyncpg
        raw_db_url = self.DATABASE_URL

        if not self.DATABASE_URL:
            self.DATABASE_URL = (
                f"postgresql+asyncpg://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}"
                f"@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
            )
        elif self.DATABASE_URL.startswith("postgresql://"):
            self.DATABASE_URL = self.DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://")
            # asyncpg requires 'ssl' instead of 'sslmode'
            self.DATABASE_URL = self.DATABASE_URL.replace("sslmode=require", "ssl=require")
            # asyncpg does not support channel_binding
            self.DATABASE_URL = self.DATABASE_URL.replace("&channel_binding=require", "")
            self.DATABASE_URL = self.DATABASE_URL.replace("?channel_binding=require", "?")

        if not self.DATABASE_URL_SYNC:
            if raw_db_url:
                self.DATABASE_URL_SYNC = raw_db_url
            else:
                self.DATABASE_URL_SYNC = (
                    f"postgresql+psycopg2://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}"
                    f"@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
                )
        
        if self.DATABASE_URL_SYNC and self.DATABASE_URL_SYNC.startswith("postgresql://"):
            self.DATABASE_URL_SYNC = self.DATABASE_URL_SYNC.replace("postgresql://", "postgresql+psycopg2://")

        # Automatically use secure for remote buckets like Cloudflare R2
        if "cloudflarestorage.com" in self.MINIO_ENDPOINT or "amazonaws.com" in self.MINIO_ENDPOINT:
            self.MINIO_SECURE = True
            
        # MinIO python SDK crashes if endpoint contains http:// or https://
        self.MINIO_ENDPOINT = self.MINIO_ENDPOINT.replace("https://", "").replace("http://", "").rstrip("/")

    # ── JWT ──────────────────────────────────────────────────────────────
    JWT_SECRET_KEY: str = "change-this-to-a-long-random-string-in-production"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    REFRESH_TOKEN_EXPIRE_DAYS: int = 30

    # ── App ──────────────────────────────────────────────────────────────
    ENVIRONMENT: str = "development"
    LOG_LEVEL: str = "INFO"
    SENTRY_DSN: str | None = None
    MAX_UPLOAD_SIZE_MB: int = 200
    BACKEND_CORS_ORIGINS: str = "http://localhost:3000"
    BACKEND_HOST: str = "0.0.0.0"
    BACKEND_PORT: int = 8000

    @property
    def MAX_UPLOAD_SIZE_BYTES(self) -> int:
        return self.MAX_UPLOAD_SIZE_MB * 1024 * 1024

    @property
    def cors_origins(self) -> list[str]:
        if self.BACKEND_CORS_ORIGINS == "*":
            return ["*"]
        return [o.strip() for o in self.BACKEND_CORS_ORIGINS.split(",")]


settings = Settings()
