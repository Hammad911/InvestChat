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
    ollama_model: str | None = None
    embed_model: str | None = None


@router.get("/health", response_model=HealthResponse)
async def health_check():
    """Check connectivity and status of all services."""
    services: list[ServiceStatus] = []
    overall_healthy = True
    ollama_model = None
    embed_model = None

    # ── Ollama ────────────────────────────────────────────────────────
    try:
        resp = httpx.get(
            f"{settings.OLLAMA_BASE_URL}/api/tags",
            timeout=5,
        )
        resp.raise_for_status()
        models = resp.json().get("models", [])
        model_names = [m.get("name", "") for m in models]

        llm_ready = any(settings.OLLAMA_LLM_MODEL in n for n in model_names)
        embed_ready = any(settings.OLLAMA_EMBED_MODEL in n for n in model_names)

        if llm_ready and embed_ready:
            ollama_status = "healthy"
            ollama_model = settings.OLLAMA_LLM_MODEL
            embed_model = settings.OLLAMA_EMBED_MODEL
        else:
            ollama_status = "degraded"
            overall_healthy = False

        services.append(ServiceStatus(
            name="ollama",
            status=ollama_status,
            details={
                "models_available": model_names,
                "llm_model_ready": llm_ready,
                "embed_model_ready": embed_ready,
            },
        ))
    except Exception as e:
        services.append(ServiceStatus(
            name="ollama", status="unhealthy", details={"error": str(e)}
        ))
        overall_healthy = False

    # ── Qdrant ────────────────────────────────────────────────────────
    try:
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
        ollama_model=ollama_model,
        embed_model=embed_model,
    )
