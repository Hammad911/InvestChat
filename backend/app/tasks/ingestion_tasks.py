"""
Celery task definitions for async document ingestion.
"""
from __future__ import annotations

from celery import Celery

from app.core.config import settings

# ── Celery App ───────────────────────────────────────────────────────────────
celery_app = Celery(
    "dd_copilot",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_acks_late=True,  # Tasks acknowledged after completion (idempotency)
    worker_prefetch_multiplier=1,
    task_reject_on_worker_lost=True,
    task_default_retry_delay=30,
    task_max_retries=3,
)


@celery_app.task(
    bind=True,
    name="ingest_document",
    max_retries=10,
    default_retry_delay=60,
    acks_late=True,
)
def ingest_document(self, document_id: str) -> dict:
    """
    Async Celery task to ingest a document.
    Idempotent — safe to retry on failure.
    """
    from app.core.logging import get_logger
    from app.ingestion.pipeline import run_ingestion_pipeline

    logger = get_logger(__name__)

    try:
        logger.info(
            "celery_task_start",
            task_id=self.request.id,
            document_id=document_id,
        )
        run_ingestion_pipeline(document_id)
        return {"status": "success", "document_id": document_id}

    except Exception as exc:
        logger.error(
            "celery_task_failed",
            task_id=self.request.id,
            document_id=document_id,
            error=str(exc),
            retry=self.request.retries,
        )
        raise self.retry(exc=exc)
