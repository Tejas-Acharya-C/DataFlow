"""Data transformation endpoints (preview and apply)."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from dataflow.api.deps import get_db, get_transformation_service
from dataflow.models.dataset import DatasetVersion
from dataflow.schemas.transformation import (
    TransformationApplyResponse,
    TransformationPreviewResponse,
    TransformationRequest,
)
from dataflow.services.transformation import TransformationError, TransformationService

router = APIRouter(prefix="/transformations", tags=["Transformations"])


@router.post("/preview", response_model=TransformationPreviewResponse)
def preview_transformation(
    payload: TransformationRequest,
    db: Session = Depends(get_db),
    service: TransformationService = Depends(get_transformation_service),
):
    """Preview transformation results on sample rows without modifying or creating versions."""
    version = db.get(DatasetVersion, payload.version_id)
    if not version or version.dataset_id != payload.dataset_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Dataset version not found.")

    try:
        preview = service.preview_transformation(
            version=version,
            operations=payload.operations,
        )
        return TransformationPreviewResponse(**preview)
    except TransformationError as te:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(te))
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Transformation preview failed: {exc}",
        )


@router.post("/apply", response_model=TransformationApplyResponse, status_code=status.HTTP_201_CREATED)
def apply_transformation(
    payload: TransformationRequest,
    db: Session = Depends(get_db),
    service: TransformationService = Depends(get_transformation_service),
):
    """Apply safe transformations and persist a new immutable dataset version."""
    version = db.get(DatasetVersion, payload.version_id)
    if not version or version.dataset_id != payload.dataset_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Dataset version not found.")

    try:
        new_version = service.apply_transformation(
            db=db,
            version=version,
            operations=payload.operations,
            reason=payload.reason,
        )
        return TransformationApplyResponse(
            dataset_id=new_version.dataset_id,
            new_version_id=new_version.id,
            version_number=new_version.version_number,
            parent_version_id=version.id,
            row_count=new_version.row_count,
            column_count=new_version.column_count,
            checksum=new_version.checksum,
            created_at=str(new_version.created_at),
        )
    except TransformationError as te:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(te))
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Transformation execution failed: {exc}",
        )
