"""
Celery task definitions for async document ingestion.
Also includes the nightly clean_orphaned_vectors maintenance task.
"""
from __future__ import annotations

from celery import Celery

import ssl
from app.core.config import settings

# ── Sentry ───────────────────────────────────────────────────────────────────
import sentry_sdk

if settings.SENTRY_DSN:
    sentry_sdk.init(
        dsn=settings.SENTRY_DSN,
        environment=settings.ENVIRONMENT,
        traces_sample_rate=1.0,
        profiles_sample_rate=1.0,
    )

# Automatically handle secure Redis connections (Upstash rediss://)
ssl_options = None
if settings.REDIS_URL and settings.REDIS_URL.startswith("rediss://"):
    ssl_options = {"ssl_cert_reqs": ssl.CERT_NONE}

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
    broker_use_ssl=ssl_options,
    redis_backend_use_ssl=ssl_options,
)


def _daily_at_2am():
    """Return a crontab schedule for 02:00 UTC daily."""
    from celery.schedules import crontab
    return crontab(hour=2, minute=0)


# Set beat schedule after helper function is defined
celery_app.conf.beat_schedule = {
    "clean-orphaned-vectors-nightly": {
        "task": "clean_orphaned_vectors",
        "schedule": _daily_at_2am(),
    },
}



# ── Ingestion task ────────────────────────────────────────────────────────────

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

        # Invalidate analysis cache for this project so next analysis
        # request picks up the newly ingested document
        try:
            from app.core.semantic_cache import invalidate_project_cache
            # We need the project_id from the document — look it up sync
            from sqlalchemy import create_engine, text
            sync_engine = create_engine(settings.DATABASE_URL_SYNC, pool_pre_ping=True)
            with sync_engine.connect() as conn:
                row = conn.execute(
                    text("SELECT project_id FROM documents WHERE id = :doc_id"),
                    {"doc_id": document_id},
                ).fetchone()
                if row:
                    invalidate_project_cache(str(row[0]))
        except Exception as cache_exc:
            # Non-fatal — cache will expire on its own TTL
            logger.warning(
                "cache_invalidation_failed",
                document_id=document_id,
                error=str(cache_exc),
            )

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


# ── Nightly orphan cleanup task ───────────────────────────────────────────────

@celery_app.task(
    bind=True,
    name="clean_orphaned_vectors",
    max_retries=3,
    default_retry_delay=300,
)
def clean_orphaned_vectors(self) -> dict:
    """
    Nightly maintenance: cross-reference PostgreSQL document IDs against
    Qdrant point payloads and delete any vectors whose source document no
    longer exists in the database.

    This handles the edge case where MinIO deletion succeeds but Qdrant
    deletion fails, or where a document was deleted directly from the DB
    without going through the API.

    Runs at 02:00 UTC via Celery Beat.
    """
    from app.core.logging import get_logger
    from app.ingestion.embedder import get_qdrant_client
    from sqlalchemy import create_engine, text
    from sqlalchemy.orm import sessionmaker
    from qdrant_client.models import Filter, FieldCondition, MatchAny
    import uuid

    logger = get_logger(__name__)
    logger.info("orphan_cleanup_start")

    deleted_count = 0
    error_count = 0

    try:
        # ── Fetch all live document IDs from PostgreSQL ───────────────────
        sync_engine = create_engine(settings.DATABASE_URL_SYNC, pool_pre_ping=True)
        SyncSession = sessionmaker(bind=sync_engine)
        db = SyncSession()
        try:
            rows = db.execute(text("SELECT id FROM documents")).fetchall()
            live_doc_ids = {str(row[0]) for row in rows}
        finally:
            db.close()
            sync_engine.dispose()

        logger.info(
            "orphan_cleanup_db_fetched", live_doc_count=len(live_doc_ids)
        )

        if not live_doc_ids:
            logger.warning("orphan_cleanup_no_live_docs_skipping")
            return {"deleted": 0, "errors": 0}

        # ── Scroll through all Qdrant points and find orphaned doc_ids ────
        client = get_qdrant_client()
        orphaned_doc_ids: set[str] = set()
        offset = None
        batch_size = 1000
        total_points_scanned = 0

        while True:
            scroll_result, next_offset = client.scroll(
                collection_name=settings.QDRANT_COLLECTION,
                limit=batch_size,
                offset=offset,
                with_payload=["doc_id"],
                with_vectors=False,
            )

            total_points_scanned += len(scroll_result)

            for point in scroll_result:
                doc_id = (point.payload or {}).get("doc_id")
                if doc_id and doc_id not in live_doc_ids:
                    orphaned_doc_ids.add(doc_id)

            if next_offset is None:
                break
            offset = next_offset

        logger.info(
            "orphan_cleanup_scan_complete",
            total_points_scanned=total_points_scanned,
            orphaned_doc_ids_found=len(orphaned_doc_ids),
        )

        # ── Delete orphaned vectors in batches ────────────────────────────
        from app.ingestion.embedder import delete_document_vectors

        for doc_id in orphaned_doc_ids:
            try:
                delete_document_vectors(doc_id)
                deleted_count += 1
                logger.info("orphan_vectors_deleted", doc_id=doc_id)
            except Exception as exc:
                error_count += 1
                logger.error(
                    "orphan_delete_failed",
                    doc_id=doc_id,
                    error=str(exc),
                )

        logger.info(
            "orphan_cleanup_complete",
            deleted_doc_ids=deleted_count,
            errors=error_count,
        )
        return {"deleted": deleted_count, "errors": error_count}

    except Exception as exc:
        logger.error("orphan_cleanup_failed", error=str(exc), exc_info=True)
        raise self.retry(exc=exc)
