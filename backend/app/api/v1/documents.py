"""
Document management API routes with file upload and ingestion status SSE.
"""
from __future__ import annotations

import io
import uuid
from datetime import datetime
from pathlib import Path
from uuid import UUID

from pydantic import BaseModel
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import settings
from app.core.logging import get_logger
from app.core.security import get_current_user
from app.db.models import DocType, Document, IngestionEvent, IngestionStatus, Project, User
from app.db.session import get_db
from app.storage.minio_client import upload_file, delete_file
from app.tasks.ingestion_tasks import ingest_document

logger = get_logger(__name__)

router = APIRouter(prefix="/projects/{project_id}/documents", tags=["documents"])

ALLOWED_EXTENSIONS = {".pdf", ".docx", ".pptx", ".xlsx", ".txt"}
CONTENT_TYPE_MAP = {
    ".pdf": "application/pdf",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ".pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    ".txt": "text/plain",
}


# ── Schemas ──────────────────────────────────────────────────────────────────


class DocumentResponse(BaseModel):
    id: str
    filename: str
    original_filename: str
    doc_type: str
    file_size: int
    page_count: int | None
    ingestion_status: str
    chunk_count: int
    error_message: str | None
    uploaded_at: datetime
    ingested_at: datetime | None

    class Config:
        from_attributes = True


class DocumentListResponse(BaseModel):
    documents: list[DocumentResponse]
    total: int


# ── Helpers ──────────────────────────────────────────────────────────────────


async def _get_project_or_404(
    project_id: UUID, user: User, db: AsyncSession
) -> Project:
    result = await db.execute(
        select(Project).where(Project.id == project_id, Project.user_id == user.id)
    )
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return project


def _doc_to_response(doc: Document) -> DocumentResponse:
    return DocumentResponse(
        id=str(doc.id),
        filename=doc.filename,
        original_filename=doc.original_filename,
        doc_type=doc.doc_type.value if doc.doc_type else "other",
        file_size=doc.file_size,
        page_count=doc.page_count,
        ingestion_status=doc.ingestion_status.value if doc.ingestion_status else "pending",
        chunk_count=doc.chunk_count,
        error_message=doc.error_message,
        uploaded_at=doc.uploaded_at,
        ingested_at=doc.ingested_at,
    )


# ── Routes ───────────────────────────────────────────────────────────────────


@router.get("", response_model=DocumentListResponse)
async def list_documents(
    project_id: UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """List all documents in a project."""
    await _get_project_or_404(project_id, user, db)
    result = await db.execute(
        select(Document)
        .where(Document.project_id == project_id)
        .order_by(Document.uploaded_at.desc())
    )
    docs = result.scalars().all()
    return DocumentListResponse(
        documents=[_doc_to_response(d) for d in docs],
        total=len(docs),
    )


@router.post("", response_model=DocumentResponse, status_code=status.HTTP_201_CREATED)
async def upload_document(
    project_id: UUID,
    file: UploadFile = File(...),
    doc_type: str = Form(default="other"),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Upload a document and trigger async ingestion."""
    project = await _get_project_or_404(project_id, user, db)

    # Validate file extension
    ext = Path(file.filename or "").suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type: {ext}. Allowed: {', '.join(ALLOWED_EXTENSIONS)}",
        )

    # Read file and validate size
    file_bytes = await file.read()
    if len(file_bytes) > settings.MAX_UPLOAD_SIZE_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"File exceeds maximum size of {settings.MAX_UPLOAD_SIZE_MB}MB",
        )

    # Generate unique filename
    file_id = str(uuid.uuid4())
    stored_filename = f"{project_id}/{file_id}{ext}"

    # Upload to MinIO
    upload_file(
        object_name=stored_filename,
        data=io.BytesIO(file_bytes),
        length=len(file_bytes),
        content_type=CONTENT_TYPE_MAP.get(ext, "application/octet-stream"),
    )

    # Parse doc_type enum
    try:
        dtype = DocType(doc_type)
    except ValueError:
        dtype = DocType.OTHER

    # Create DB record
    doc = Document(
        project_id=project_id,
        filename=stored_filename,
        original_filename=file.filename or "untitled",
        doc_type=dtype,
        file_path=stored_filename,
        file_size=len(file_bytes),
        ingestion_status=IngestionStatus.PENDING,
    )
    db.add(doc)
    await db.flush()

    # Dispatch Celery ingestion task
    ingest_document.delay(str(doc.id))

    logger.info(
        "document_uploaded",
        doc_id=str(doc.id),
        filename=file.filename,
        size=len(file_bytes),
    )

    return _doc_to_response(doc)


@router.get("/{doc_id}", response_model=DocumentResponse)
async def get_document(
    project_id: UUID,
    doc_id: UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Get document metadata and status."""
    await _get_project_or_404(project_id, user, db)
    result = await db.execute(
        select(Document).where(
            Document.id == doc_id, Document.project_id == project_id
        )
    )
    doc = result.scalar_one_or_none()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    return _doc_to_response(doc)


@router.delete("/{doc_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_document(
    project_id: UUID,
    doc_id: UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """
    Delete a document atomically across Qdrant, MinIO, and PostgreSQL.

    Ordering and rollback strategy:
    1. Delete vectors from Qdrant FIRST — if this fails, DB record is untouched
       and we can raise a clean 500 without leaving orphaned vectors.
    2. Delete file from MinIO — non-fatal if this fails (storage can be
       reconciled separately). Log the error and proceed.
    3. Hard-delete the DB record — always last, so Qdrant is never orphaned.
    """
    await _get_project_or_404(project_id, user, db)
    result = await db.execute(
        select(Document).where(
            Document.id == doc_id, Document.project_id == project_id
        )
    )
    doc = result.scalar_one_or_none()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    doc_id_str = str(doc.id)

    # ── Step 1: Delete from Qdrant (must succeed before DB delete) ───────────
    try:
        from app.ingestion.embedder import delete_document_vectors
        delete_document_vectors(doc_id_str)
        logger.info("qdrant_vectors_deleted", doc_id=doc_id_str)
    except Exception as e:
        logger.error(
            "qdrant_delete_failed",
            doc_id=doc_id_str,
            error=str(e),
        )
        raise HTTPException(
            status_code=500,
            detail="Failed to delete document vectors. Document record preserved. Please retry.",
        )

    # ── Step 2: Delete from MinIO (best-effort — log and continue) ───────────
    try:
        delete_file(doc.file_path)
        logger.info("minio_file_deleted", doc_id=doc_id_str, file_path=doc.file_path)
    except Exception as e:
        # Non-fatal: vectors are gone, so retrieval is clean.
        # The storage file will be reconciled by clean_orphaned_vectors task.
        logger.warning(
            "minio_delete_failed_continuing",
            doc_id=doc_id_str,
            file_path=doc.file_path,
            error=str(e),
        )

    # ── Step 3: Delete from PostgreSQL (cascades to IngestionEvents) ─────────
    await db.delete(doc)
    logger.info("document_db_deleted", doc_id=doc_id_str)


@router.get("/{doc_id}/status")
async def document_status_stream(
    project_id: UUID,
    doc_id: UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """SSE stream of document ingestion events."""
    await _get_project_or_404(project_id, user, db)

    async def event_generator():
        import asyncio

        last_count = 0
        max_polls = 300  # 5 minutes max
        poll = 0

        while poll < max_polls:
            result = await db.execute(
                select(IngestionEvent)
                .where(IngestionEvent.document_id == doc_id)
                .order_by(IngestionEvent.created_at.asc())
            )
            events = result.scalars().all()

            # Send any new events
            for event in events[last_count:]:
                import json
                data = json.dumps({
                    "stage": event.stage,
                    "status": event.status,
                    "message": event.message,
                    "timestamp": event.created_at.isoformat() if event.created_at else None,
                })
                yield f"data: {data}\n\n"

            last_count = len(events)

            # Check if ingestion is complete or failed
            doc_result = await db.execute(
                select(Document).where(Document.id == doc_id)
            )
            doc = doc_result.scalar_one_or_none()
            if doc and doc.ingestion_status in (
                IngestionStatus.COMPLETE,
                IngestionStatus.FAILED,
            ):
                import json
                final = json.dumps({
                    "stage": "pipeline",
                    "status": "final",
                    "message": doc.ingestion_status.value,
                    "chunk_count": doc.chunk_count,
                })
                yield f"data: {final}\n\n"
                return

            if poll % 10 == 0:
                # Send a heartbeat ping every 10 seconds to keep reverse proxies alive
                yield f"data: {{\"type\": \"ping\"}}\n\n"

            await asyncio.sleep(1)
            poll += 1

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
