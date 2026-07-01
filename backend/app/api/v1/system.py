"""
System health check and metrics API routes.
Reports status of all services: Gemini, Qdrant, PostgreSQL, Redis, MinIO.
Also exposes /system/metrics for operational telemetry.
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


# ── Metrics ───────────────────────────────────────────────────────────────────


class MetricsResponse(BaseModel):
    cache_hit_rate_1hr: float | None  # 0.0–1.0, None if no data
    avg_retrieval_latency_ms: float | None
    avg_generation_latency_ms: float | None
    celery_queue_depth: int
    total_cache_hits_1hr: int
    total_cache_misses_1hr: int


@router.get("/metrics", response_model=MetricsResponse)
async def get_metrics():
    """
    Operational metrics aggregated from Redis over the last 1 hour.

    - cache_hit_rate_1hr: fraction of analysis requests served from cache
    - avg_retrieval_latency_ms: rolling average Qdrant retrieval time
    - avg_generation_latency_ms: rolling average Gemini generation time
    - celery_queue_depth: number of tasks waiting in the Celery queue
    """
    import redis as redis_lib
    import time

    try:
        r = redis_lib.from_url(settings.REDIS_URL, decode_responses=True)

        # ── Cache hit/miss counters (last 60 minutes) ─────────────────────
        now_bucket = int(time.time() // 60)
        namespaces = ["risks", "growth", "financials", "summary"]
        total_hits = 0
        total_misses = 0

        for ns in namespaces:
            for offset in range(60):
                bucket = now_bucket - offset
                hit_key = f"metrics:cache_hit:{ns}:{bucket}"
                miss_key = f"metrics:cache_miss:{ns}:{bucket}"
                h = r.get(hit_key)
                m = r.get(miss_key)
                total_hits += int(h) if h else 0
                total_misses += int(m) if m else 0

        total_requests = total_hits + total_misses
        cache_hit_rate = (total_hits / total_requests) if total_requests > 0 else None

        # ── Latency rolling averages ──────────────────────────────────────
        def _avg_latency(stage: str) -> float | None:
            raw = r.lrange(f"metrics:latency:{stage}", 0, 999)
            if not raw:
                return None
            vals = [float(v) for v in raw if v]
            return round(sum(vals) / len(vals), 2) if vals else None

        avg_retrieval = _avg_latency("retrieval")
        avg_generation = _avg_latency("generation")

        # ── Celery queue depth ────────────────────────────────────────────
        # Celery tasks live in the "celery" list in Redis DB 0
        celery_queue_depth = r.llen("celery") or 0

        return MetricsResponse(
            cache_hit_rate_1hr=round(cache_hit_rate, 4) if cache_hit_rate is not None else None,
            avg_retrieval_latency_ms=avg_retrieval,
            avg_generation_latency_ms=avg_generation,
            celery_queue_depth=celery_queue_depth,
            total_cache_hits_1hr=total_hits,
            total_cache_misses_1hr=total_misses,
        )

    except Exception as exc:
        logger.error("metrics_fetch_error", error=str(exc))
        return MetricsResponse(
            cache_hit_rate_1hr=None,
            avg_retrieval_latency_ms=None,
            avg_generation_latency_ms=None,
            celery_queue_depth=0,
            total_cache_hits_1hr=0,
            total_cache_misses_1hr=0,
        )
