"""Data profiling endpoints."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from dataflow.api.deps import get_db, get_profiling_service
from dataflow.models.dataset import DatasetVersion
from dataflow.models.profiling import ProfilingResult
from dataflow.schemas.profiling import ProfilingResponse
from dataflow.services.profiling import ProfilingService

router = APIRouter(prefix="/profiling", tags=["Profiling"])


@router.post("/{version_id}", response_model=ProfilingResponse, status_code=status.HTTP_200_OK)
def run_profiling(
    version_id: str,
    db: Session = Depends(get_db),
    service: ProfilingService = Depends(get_profiling_service),
):
    """Execute statistical profiling on a dataset version."""
    version = db.get(DatasetVersion, version_id)
    if not version:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Dataset version not found.")

    try:
        result = service.profile_version(db=db, version=version)
        return result
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Profiling failed: {exc}",
        )


@router.get("/{version_id}", response_model=ProfilingResponse)
def get_profiling(
    version_id: str,
    db: Session = Depends(get_db),
    service: ProfilingService = Depends(get_profiling_service),
):
    """Retrieve profiling results for a version (runs automatically if not yet profiled)."""
    version = db.get(DatasetVersion, version_id)
    if not version:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Dataset version not found.")

    result = db.scalar(select(ProfilingResult).where(ProfilingResult.version_id == version_id))
    if not result:
        # Generate on demand
        result = service.profile_version(db=db, version=version)

    return result
