"""
Analysis API routes — triggers and retrieves AI analysis runs.
Rate-limited per IP via slowapi. Request IDs propagated to analysis modules.
"""
from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from pydantic import BaseModel
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import settings
from app.core.security import get_current_user
from app.db.models import AnalysisRun, AnalysisType, Document, Project, RunStatus, User
from app.db.session import get_db
from app.main import limiter

router = APIRouter(prefix="/projects/{project_id}/analysis", tags=["analysis"])


# ── Schemas ──────────────────────────────────────────────────────────────────


class AnalysisRequest(BaseModel):
    pass  # No body needed — analysis type is in the URL


class AnalysisResponse(BaseModel):
    id: str
    run_type: str
    status: str
    result: dict | None
    model_used: str | None
    created_at: datetime
    completed_at: datetime | None

    class Config:
        from_attributes = True


# ── Helpers ──────────────────────────────────────────────────────────────────


async def _get_project_or_404(
    project_id: UUID, user: User, db: AsyncSession
) -> Project:
    result = await db.execute(
        select(Project)
        .where(Project.id == project_id, Project.user_id == user.id)
        .options(selectinload(Project.documents))
    )
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return project


def _get_doc_name_map(documents: list[Document]) -> dict[str, str]:
    return {str(d.id): d.original_filename for d in documents}


async def _run_analysis(
    project: Project,
    analysis_type: AnalysisType,
    db: AsyncSession,
    request_id: str | None = None,
) -> AnalysisResponse:
    """Run an analysis and persist the result."""
    from app.analysis.risks import analyze_risks
    from app.analysis.growth import analyze_growth
    from app.analysis.financials import analyze_financials
    from app.analysis.summary import analyze_summary

    run = AnalysisRun(
        project_id=project.id,
        run_type=analysis_type,
        status=RunStatus.RUNNING,
    )
    db.add(run)
    await db.flush()

    doc_name_map = _get_doc_name_map(project.documents)
    project_id_str = str(project.id)

    try:
        if analysis_type == AnalysisType.RISKS:
            result = await analyze_risks(project_id_str, doc_name_map, request_id=request_id)
        elif analysis_type == AnalysisType.GROWTH:
            result = await analyze_growth(project_id_str, doc_name_map, request_id=request_id)
        elif analysis_type == AnalysisType.FINANCIALS:
            result = await analyze_financials(project_id_str, doc_name_map, request_id=request_id)
        elif analysis_type == AnalysisType.SUMMARY:
            result = await analyze_summary(project_id_str, doc_name_map, request_id=request_id)
        else:
            raise ValueError(f"Unknown analysis type: {analysis_type}")

        run.result_json = result
        run.status = RunStatus.COMPLETE
        run.model_used = result.get("model_used")
        run.completed_at = datetime.now(timezone.utc)
        await db.flush()

    except HTTPException:
        run.status = RunStatus.FAILED
        run.result_json = {"error": "upstream_error"}
        run.completed_at = datetime.now(timezone.utc)
        await db.flush()
        raise  # re-raise 504/429 directly — already clean HTTP errors

    except Exception as e:
        run.status = RunStatus.FAILED
        run.result_json = {"error": str(e)}
        run.completed_at = datetime.now(timezone.utc)
        await db.flush()
        raise HTTPException(status_code=500, detail=f"Analysis failed: {str(e)}")

    return AnalysisResponse(
        id=str(run.id),
        run_type=run.run_type.value,
        status=run.status.value,
        result=run.result_json,
        model_used=run.model_used,
        created_at=run.created_at,
        completed_at=run.completed_at,
    )


# ── Routes ───────────────────────────────────────────────────────────────────


@router.post("/risks", response_model=AnalysisResponse)
@limiter.limit(f"{settings.RATE_LIMIT_PER_MINUTE}/minute")
async def run_risk_analysis(
    request: Request,
    project_id: UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Run risk assessment analysis."""
    project = await _get_project_or_404(project_id, user, db)
    request_id = getattr(request.state, "request_id", None)
    return await _run_analysis(project, AnalysisType.RISKS, db, request_id=request_id)


@router.post("/growth", response_model=AnalysisResponse)
@limiter.limit(f"{settings.RATE_LIMIT_PER_MINUTE}/minute")
async def run_growth_analysis(
    request: Request,
    project_id: UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Run growth opportunities analysis."""
    project = await _get_project_or_404(project_id, user, db)
    request_id = getattr(request.state, "request_id", None)
    return await _run_analysis(project, AnalysisType.GROWTH, db, request_id=request_id)


@router.post("/financials", response_model=AnalysisResponse)
@limiter.limit(f"{settings.RATE_LIMIT_PER_MINUTE}/minute")
async def run_financial_analysis(
    request: Request,
    project_id: UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Run financial metrics extraction."""
    project = await _get_project_or_404(project_id, user, db)
    request_id = getattr(request.state, "request_id", None)
    return await _run_analysis(project, AnalysisType.FINANCIALS, db, request_id=request_id)


@router.post("/summary", response_model=AnalysisResponse)
@limiter.limit(f"{settings.RATE_LIMIT_PER_MINUTE}/minute")
async def run_summary_analysis(
    request: Request,
    project_id: UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Generate executive summary."""
    project = await _get_project_or_404(project_id, user, db)
    request_id = getattr(request.state, "request_id", None)
    return await _run_analysis(project, AnalysisType.SUMMARY, db, request_id=request_id)


@router.get("/{run_id}", response_model=AnalysisResponse)
async def get_analysis_result(
    project_id: UUID,
    run_id: UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Get a specific analysis run result."""
    await _get_project_or_404(project_id, user, db)
    result = await db.execute(
        select(AnalysisRun).where(
            AnalysisRun.id == run_id, AnalysisRun.project_id == project_id
        )
    )
    run = result.scalar_one_or_none()
    if not run:
        raise HTTPException(status_code=404, detail="Analysis run not found")

    return AnalysisResponse(
        id=str(run.id),
        run_type=run.run_type.value,
        status=run.status.value,
        result=run.result_json,
        model_used=run.model_used,
        created_at=run.created_at,
        completed_at=run.completed_at,
    )
