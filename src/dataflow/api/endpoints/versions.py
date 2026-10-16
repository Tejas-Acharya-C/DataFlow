"""Dataset versions and comparison endpoints."""

from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from dataflow.api.deps import get_db, get_storage_manager
from dataflow.models.dataset import DatasetVersion
from dataflow.schemas.dataset import DatasetVersionResponse, VersionCompareResponse
from dataflow.services.lineage import compare_versions
from dataflow.storage.local import LocalStorageManager

router = APIRouter(prefix="/versions", tags=["Versions"])


class CompareRequest(BaseModel):
    version_a_id: str
    version_b_id: str


@router.get("/dataset/{dataset_id}", response_model=List[DatasetVersionResponse])
def list_dataset_versions(
    dataset_id: str,
    db: Session = Depends(get_db),
):
    """List all immutable versions of a dataset ordered by version number descending."""
    versions = db.scalars(
        select(DatasetVersion)
        .where(DatasetVersion.dataset_id == dataset_id)
        .order_by(DatasetVersion.version_number.desc())
    ).all()
    return [DatasetVersionResponse.model_validate(v) for v in versions]


@router.get("/{version_id}", response_model=DatasetVersionResponse)
def get_version(
    version_id: str,
    db: Session = Depends(get_db),
):
    """Get metadata for a specific dataset version."""
    version = db.get(DatasetVersion, version_id)
    if not version:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Version not found.")
    return DatasetVersionResponse.model_validate(version)


@router.get("/{version_id}/download")
def download_version(
    version_id: str,
    db: Session = Depends(get_db),
    storage: LocalStorageManager = Depends(get_storage_manager),
):
    """Download the specific CSV file artifact associated with this version."""
    version = db.get(DatasetVersion, version_id)
    if not version:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Version not found.")

    return StreamingResponse(
        storage.file_stream(version.storage_path),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{version.original_filename}"'},
    )


@router.post("/compare", response_model=VersionCompareResponse)
def compare_dataset_versions(
    payload: CompareRequest,
    db: Session = Depends(get_db),
):
    """Compare schema, columns, and row counts between two versions."""
    va = db.get(DatasetVersion, payload.version_a_id)
    vb = db.get(DatasetVersion, payload.version_b_id)
    if not va or not vb:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="One or both versions not found.")

    diff = compare_versions(va, vb)
    return VersionCompareResponse(**diff)
