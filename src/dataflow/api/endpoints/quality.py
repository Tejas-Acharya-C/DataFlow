"""Data quality evaluation endpoints."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from dataflow.api.deps import get_db, get_quality_service
from dataflow.models.dataset import DatasetVersion
from dataflow.models.profiling import QualityResult
from dataflow.schemas.quality import QualityEvaluationResponse
from dataflow.services.quality import QualityService

router = APIRouter(prefix="/quality", tags=["Data Quality"])


@router.post("/{version_id}", response_model=QualityEvaluationResponse, status_code=status.HTTP_200_OK)
def evaluate_quality(
    version_id: str,
    db: Session = Depends(get_db),
    service: QualityService = Depends(get_quality_service),
):
    """Run data quality evaluation and generate deterministic score for a dataset version."""
    version = db.get(DatasetVersion, version_id)
    if not version:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Dataset version not found.")

    try:
        result = service.evaluate_version(db=db, version=version)
        return result
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Quality evaluation failed: {exc}",
        )


@router.get("/{version_id}", response_model=QualityEvaluationResponse)
def get_quality(
    version_id: str,
    db: Session = Depends(get_db),
    service: QualityService = Depends(get_quality_service),
):
    """Retrieve quality score and check breakdown (evaluates on demand if not yet evaluated)."""
    version = db.get(DatasetVersion, version_id)
    if not version:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Dataset version not found.")

    result = db.scalar(select(QualityResult).where(QualityResult.version_id == version_id))
    if not result:
        result = service.evaluate_version(db=db, version=version)

    return result
