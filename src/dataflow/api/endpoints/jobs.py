"""Processing jobs and status tracking endpoints."""

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from dataflow.api.deps import get_db
from dataflow.models.job import ProcessingJob
from dataflow.schemas.job import JobListResponse, JobResponse

router = APIRouter(prefix="/jobs", tags=["Jobs"])


@router.get("", response_model=JobListResponse)
def list_jobs(
    status_filter: Optional[str] = Query(None, alias="status"),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    db: Session = Depends(get_db),
):
    """List execution jobs with optional status filter."""
    stmt = select(ProcessingJob)
    if status_filter:
        stmt = stmt.where(ProcessingJob.status == status_filter)

    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    jobs = db.scalars(
        stmt.order_by(ProcessingJob.created_at.desc()).offset(skip).limit(limit)
    ).all()

    return JobListResponse(
        items=[JobResponse.model_validate(j) for j in jobs],
        total=total,
    )


@router.get("/{job_id}", response_model=JobResponse)
def get_job(
    job_id: str,
    db: Session = Depends(get_db),
):
    """Retrieve details and status for a processing job."""
    job = db.get(ProcessingJob, job_id)
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found.")
    return job
