"""
AI Due Diligence Copilot — FastAPI Application Entry Point.
"""
from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

import uuid
import structlog

from app.core.config import settings
from app.core.logging import setup_logging, get_logger

logger = get_logger(__name__)


# ── Request ID Middleware ─────────────────────────────────────────────────────
class RequestIdMiddleware(BaseHTTPMiddleware):
    """
    Generates a unique request_id for every incoming request.
    - Binds request_id to the structlog context so ALL log lines within
      the same request automatically include it.
    - Echoes it back in the X-Request-ID response header.
    """

    async def dispatch(self, request: Request, call_next) -> Response:
        request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
        # Store on request.state so route handlers can access it
        request.state.request_id = request_id
        # Bind to structlog context for this async task
        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(request_id=request_id)
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        return response


# ── Rate Limiter ─────────────────────────────────────────────────────────────
limiter = Limiter(key_func=get_remote_address)


# ── Sentry ───────────────────────────────────────────────────────────────────
import sentry_sdk

if settings.SENTRY_DSN:
    sentry_sdk.init(
        dsn=settings.SENTRY_DSN,
        environment=settings.ENVIRONMENT,
        traces_sample_rate=1.0,
        profiles_sample_rate=1.0,
    )

# ── Lifespan ─────────────────────────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown events."""
    setup_logging()
    logger.info("application_startup", environment=settings.ENVIRONMENT)

    # Initialize Qdrant collection
    try:
        from app.ingestion.embedder import ensure_collection
        ensure_collection()
    except Exception as e:
        logger.warning("qdrant_init_failed", error=str(e))

    # Initialize MinIO bucket
    try:
        from app.storage.minio_client import ensure_bucket
        ensure_bucket()
    except Exception as e:
        logger.warning("minio_init_failed", error=str(e))

    # Create DB tables (for development — use Alembic in production)
    try:
        from app.db.models import Base
        from app.db.session import engine
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        logger.info("database_tables_created")
    except Exception as e:
        logger.error("database_init_failed", error=str(e))

    yield

    # Shutdown
    from app.db.session import engine
    await engine.dispose()
    logger.info("application_shutdown")


# ── App ──────────────────────────────────────────────────────────────────────
app = FastAPI(
    title="AI Due Diligence Copilot",
    description="Production-grade RAG platform for investment due diligence",
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

# Rate limiting
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Request ID — must be added AFTER CORS so it runs first (Starlette reverses order)
app.add_middleware(RequestIdMiddleware)



# ── Error Handlers ───────────────────────────────────────────────────────────
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error("unhandled_exception", path=request.url.path, error=str(exc))
    return JSONResponse(
        status_code=500,
        content={
            "error": "internal_server_error",
            "detail": str(exc) if settings.ENVIRONMENT == "development" else "An unexpected error occurred",
            "code": 500,
        },
    )


# ── Routes ───────────────────────────────────────────────────────────────────
from app.api.v1.auth import router as auth_router
from app.api.v1.projects import router as projects_router
from app.api.v1.documents import router as documents_router
from app.api.v1.analysis import router as analysis_router
from app.api.v1.chat import router as chat_router
from app.api.v1.system import router as system_router

app.include_router(auth_router, prefix="/api/v1")
app.include_router(projects_router, prefix="/api/v1")
app.include_router(documents_router, prefix="/api/v1")
app.include_router(analysis_router, prefix="/api/v1")
app.include_router(chat_router, prefix="/api/v1")
app.include_router(system_router, prefix="/api/v1")


@app.get("/")
async def root():
    return {
        "name": "AI Due Diligence Copilot",
        "version": "1.0.0",
        "docs": "/docs",
        "health": "/api/v1/system/health",
    }
