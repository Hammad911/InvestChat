"""
System health check API route.
Reports status of all services: Ollama, Qdrant, PostgreSQL, Redis, MinIO.
"""
from __future__ import annotations

from pydantic import BaseModel
import httpx
from fastapi import APIRouter

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/system", tags=["system"])


class ServiceStatus(BaseModel):
    name: str
    status: str  # "healthy" | "unhealthy" | "degraded"
    details: dict | None = None


class HealthResponse(BaseModel):
    status: str  # "healthy" | "degraded" | "unhealthy"
    services: list[ServiceStatus]
    llm_model: str | None = None
    embed_model: str | None = None


@router.get("/health", response_model=HealthResponse)
async def health_check():
    """Check connectivity and status of all services."""
    services: list[ServiceStatus] = []
    overall_healthy = True
    llm_model = None
    embed_model = None

    # ── Gemini ────────────────────────────────────────────────────────
    try:
        from google import genai
        client = genai.Client(api_key=settings.GEMINI_API_KEY)
        client.models.get(model=settings.GEMINI_LLM_MODEL)
        
        services.append(ServiceStatus(
            name="gemini",
            status="healthy",
            details={"message": "Connected to Gemini API"},
        ))
        llm_model = settings.GEMINI_LLM_MODEL
        embed_model = settings.GEMINI_EMBED_MODEL
    except Exception as e:
        services.append(ServiceStatus(
            name="gemini", status="unhealthy", details={"error": str(e)}
        ))
        overall_healthy = False

    # ── Qdrant ────────────────────────────────────────────────────────
    try:
        if settings.QDRANT_URL and settings.QDRANT_API_KEY:
            url = f"{settings.QDRANT_URL.rstrip('/')}/healthz"
            headers = {"api-key": settings.QDRANT_API_KEY}
            resp = httpx.get(url, headers=headers, timeout=5)
        else:
            resp = httpx.get(f"http://{settings.QDRANT_HOST}:{settings.QDRANT_PORT}/healthz", timeout=5)
            
        services.append(ServiceStatus(
            name="qdrant", status="healthy" if resp.status_code == 200 else "unhealthy"
        ))
    except Exception as e:
        services.append(ServiceStatus(
            name="qdrant", status="unhealthy", details={"error": str(e)}
        ))
        overall_healthy = False

    # ── PostgreSQL ────────────────────────────────────────────────────
    try:
        from sqlalchemy import text
        from app.db.session import async_session_factory

        async with async_session_factory() as session:
            await session.execute(text("SELECT 1"))
        services.append(ServiceStatus(name="postgresql", status="healthy"))
    except Exception as e:
        services.append(ServiceStatus(
            name="postgresql", status="unhealthy", details={"error": str(e)}
        ))
        overall_healthy = False

    # ── Redis ─────────────────────────────────────────────────────────
    try:
        import redis as redis_lib
        r = redis_lib.from_url(settings.REDIS_URL, socket_timeout=3)
        r.ping()
        services.append(ServiceStatus(name="redis", status="healthy"))
    except Exception as e:
        services.append(ServiceStatus(
            name="redis", status="unhealthy", details={"error": str(e)}
        ))
        overall_healthy = False

    # ── MinIO ─────────────────────────────────────────────────────────
    try:
        from app.storage.minio_client import check_health
        minio_ok = check_health()
        services.append(ServiceStatus(
            name="minio", status="healthy" if minio_ok else "unhealthy"
        ))
        if not minio_ok:
            overall_healthy = False
    except Exception as e:
        services.append(ServiceStatus(
            name="minio", status="unhealthy", details={"error": str(e)}
        ))
        overall_healthy = False

    return HealthResponse(
        status="healthy" if overall_healthy else "degraded",
        services=services,
        llm_model=llm_model,
        embed_model=embed_model,
    )
