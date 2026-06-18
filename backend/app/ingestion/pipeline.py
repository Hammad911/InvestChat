"""
Document ingestion pipeline orchestrator.
Stages: Download → Extract → Chunk → Embed → Update DB
"""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import create_engine, update
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import settings
from app.core.logging import get_logger
from app.db.models import Document, IngestionEvent, IngestionStatus
from app.ingestion.chunker import chunk_document
from app.ingestion.embedder import embed_and_store, ensure_collection
from app.ingestion.extractor import extract_document
from app.storage.minio_client import download_file

logger = get_logger(__name__)

# Sync engine for Celery workers (Celery doesn't support async natively)
sync_engine = create_engine(settings.DATABASE_URL_SYNC, pool_pre_ping=True)
SyncSessionFactory = sessionmaker(bind=sync_engine)


def _log_event(db: Session, document_id: str, stage: str, status: str, message: str = "") -> None:
    """Write an ingestion event to the database."""
    event = IngestionEvent(
        document_id=document_id,
        stage=stage,
        status=status,
        message=message,
    )
    db.add(event)
    db.commit()


def _update_status(db: Session, document_id: str, status: IngestionStatus, **kwargs) -> None:
    """Update document ingestion status."""
    values = {"ingestion_status": status, **kwargs}
    db.execute(
        update(Document).where(Document.id == document_id).values(**values)
    )
    db.commit()


def run_ingestion_pipeline(document_id: str) -> None:
    """
    Full ingestion pipeline for a single document.

    Stages:
    1. Download from MinIO
    2. Extract text + tables
    3. Chunk into hierarchical pieces
    4. Embed and store in Qdrant
    5. Update status in PostgreSQL
    """
    db = SyncSessionFactory()

    try:
        doc = db.query(Document).filter(Document.id == document_id).first()
        if not doc:
            logger.warning(
                "document_not_found_skipping",
                document_id=document_id,
                message="Document no longer exists in DB — stale task, skipping safely."
            )
            return  # Stale task — document was deleted before processing completed

        logger.info(
            "pipeline_start",
            document_id=document_id,
            filename=doc.original_filename,
            doc_type=doc.doc_type.value if doc.doc_type else "unknown",
        )

        # ── Stage 1: Download ────────────────────────────────────────
        _update_status(db, document_id, IngestionStatus.EXTRACTING)
        _log_event(db, document_id, "download", "started", "Downloading from storage")

        file_bytes = download_file(doc.file_path)
        _log_event(db, document_id, "download", "completed", f"Downloaded {len(file_bytes)} bytes")

        # ── Stage 2: Extract ─────────────────────────────────────────
        _log_event(db, document_id, "extraction", "started", "Extracting text and tables")

        extraction_result = extract_document(file_bytes, doc.original_filename)

        _update_status(
            db, document_id, IngestionStatus.EXTRACTING,
            page_count=extraction_result.page_count,
        )
        _log_event(
            db, document_id, "extraction", "completed",
            f"Extracted {len(extraction_result.elements)} elements, "
            f"{len(extraction_result.tables)} tables, "
            f"{extraction_result.page_count} pages",
        )

        # ── Stage 3: Chunk ───────────────────────────────────────────
        _update_status(db, document_id, IngestionStatus.CHUNKING)
        _log_event(db, document_id, "chunking", "started", "Creating hierarchical chunks")

        chunks = chunk_document(
            result=extraction_result,
            doc_id=str(doc.id),
            project_id=str(doc.project_id),
            doc_type=doc.doc_type.value if doc.doc_type else "other",
        )

        _log_event(
            db, document_id, "chunking", "completed",
            f"Created {len(chunks)} chunks",
        )

        # ── Stage 4: Embed ───────────────────────────────────────────
        _update_status(db, document_id, IngestionStatus.EMBEDDING)
        _log_event(db, document_id, "embedding", "started", "Generating embeddings via Gemini")

        ensure_collection()
        points_stored = embed_and_store(chunks)

        _log_event(
            db, document_id, "embedding", "completed",
            f"Stored {points_stored} vectors in Qdrant",
        )

        # ── Stage 5: Complete ────────────────────────────────────────
        _update_status(
            db, document_id, IngestionStatus.COMPLETE,
            chunk_count=len(chunks),
            ingested_at=datetime.now(timezone.utc),
        )
        _log_event(db, document_id, "pipeline", "completed", "Ingestion complete")

        logger.info(
            "pipeline_complete",
            document_id=document_id,
            chunks=len(chunks),
            vectors=points_stored,
        )

    except Exception as exc:
        logger.error(
            "pipeline_failed",
            document_id=document_id,
            error=str(exc),
            exc_info=True,
        )
        try:
            _update_status(
                db, document_id, IngestionStatus.FAILED,
                error_message=str(exc)[:2000],
            )
            _log_event(db, document_id, "pipeline", "failed", str(exc)[:2000])
        except Exception:
            pass
        raise
    finally:
        db.close()
