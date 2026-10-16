"""Dataset ingestion, listing, preview, download, and deletion endpoints."""

from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status
from fastapi.responses import StreamingResponse
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from dataflow.api.deps import get_db, get_ingestion_service, get_storage_manager
from dataflow.models.dataset import Dataset, DatasetVersion
from dataflow.schemas.dataset import (
    DatasetDetailResponse,
    DatasetListResponse,
    DatasetPreviewResponse,
    DatasetResponse,
    DatasetVersionResponse,
)
from dataflow.services.audit import log_audit
from dataflow.services.ingestion import IngestionError, IngestionService
from dataflow.storage.local import LocalStorageManager, StorageError

router = APIRouter(prefix="/datasets", tags=["Datasets"])


@router.post("/upload", response_model=DatasetDetailResponse, status_code=status.HTTP_201_CREATED)
def upload_csv(
    file: UploadFile = File(...),
    name: Optional[str] = Form(None),
    dataset_id: Optional[str] = Form(None),
    description: Optional[str] = Form(None),
    deduplicate_identical: bool = Form(True),
    db: Session = Depends(get_db),
    service: IngestionService = Depends(get_ingestion_service),
):
    """Upload a CSV file to ingest as a new dataset or new version of an existing dataset."""
    if not file.filename:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Uploaded file must have a filename.")

    try:
        dataset, version = service.ingest_csv(
            db=db,
            file_obj=file.file,
            filename=file.filename,
            dataset_name=name,
            dataset_id=dataset_id,
            description=description,
            deduplicate_identical=deduplicate_identical,
        )
    except IngestionError as ie:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(ie))
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ingestion processing error: {exc}",
        )

    # Reload dataset with versions
    db.refresh(dataset)
    return DatasetDetailResponse(
        id=dataset.id,
        name=dataset.name,
        description=dataset.description,
        is_deleted=dataset.is_deleted,
        created_at=dataset.created_at,
        updated_at=dataset.updated_at,
        latest_version=DatasetVersionResponse.model_validate(version),
        version_count=len(dataset.versions),
        versions=[DatasetVersionResponse.model_validate(v) for v in dataset.versions],
    )


@router.get("", response_model=DatasetListResponse)
def list_datasets(
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    search: Optional[str] = Query(None),
    db: Session = Depends(get_db),
):
    """List active datasets with pagination, latest version info, and search."""
    stmt = select(Dataset).where(Dataset.is_deleted == False)  # noqa: E712
    if search:
        stmt = stmt.where(Dataset.name.ilike(f"%{search}%"))

    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    datasets = db.scalars(
        stmt.order_by(Dataset.updated_at.desc()).offset(skip).limit(limit)
    ).all()

    items = []
    for d in datasets:
        latest = d.versions[0] if d.versions else None
        items.append(
            DatasetResponse(
                id=d.id,
                name=d.name,
                description=d.description,
                is_deleted=d.is_deleted,
                created_at=d.created_at,
                updated_at=d.updated_at,
                latest_version=DatasetVersionResponse.model_validate(latest) if latest else None,
                version_count=len(d.versions),
            )
        )

    return DatasetListResponse(items=items, total=total)


@router.get("/{dataset_id}", response_model=DatasetDetailResponse)
def get_dataset(
    dataset_id: str,
    db: Session = Depends(get_db),
):
    """Retrieve full dataset details including all version history."""
    dataset = db.get(Dataset, dataset_id)
    if not dataset or dataset.is_deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Dataset not found.")

    latest = dataset.versions[0] if dataset.versions else None
    return DatasetDetailResponse(
        id=dataset.id,
        name=dataset.name,
        description=dataset.description,
        is_deleted=dataset.is_deleted,
        created_at=dataset.created_at,
        updated_at=dataset.updated_at,
        latest_version=DatasetVersionResponse.model_validate(latest) if latest else None,
        version_count=len(dataset.versions),
        versions=[DatasetVersionResponse.model_validate(v) for v in dataset.versions],
    )


@router.get("/{dataset_id}/preview", response_model=DatasetPreviewResponse)
def preview_dataset(
    dataset_id: str,
    version_id: Optional[str] = Query(None),
    max_rows: int = Query(50, ge=1, le=100),
    db: Session = Depends(get_db),
    storage: LocalStorageManager = Depends(get_storage_manager),
):
    """Preview bounded rows of the specified or latest dataset version."""
    dataset = db.get(Dataset, dataset_id)
    if not dataset or dataset.is_deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Dataset not found.")

    if version_id:
        target_version = db.get(DatasetVersion, version_id)
        if not target_version or target_version.dataset_id != dataset_id:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Version not found.")
    else:
        if not dataset.versions:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Dataset has no versions.")
        target_version = dataset.versions[0]

    try:
        columns, rows, count = storage.read_preview(target_version.storage_path, max_rows=max_rows)
    except StorageError as se:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(se))

    return DatasetPreviewResponse(
        dataset_id=dataset.id,
        version_id=target_version.id,
        version_number=target_version.version_number,
        columns=columns,
        rows=rows,
        total_preview_rows=count,
        total_rows=target_version.row_count,
    )


@router.get("/{dataset_id}/download")
def download_dataset(
    dataset_id: str,
    version_id: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    storage: LocalStorageManager = Depends(get_storage_manager),
):
    """Download CSV contents of the specified or latest dataset version."""
    dataset = db.get(Dataset, dataset_id)
    if not dataset or dataset.is_deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Dataset not found.")

    if version_id:
        version = db.get(DatasetVersion, version_id)
        if not version or version.dataset_id != dataset_id:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Version not found.")
    else:
        if not dataset.versions:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Dataset has no versions.")
        version = dataset.versions[0]

    log_audit(
        db,
        event_type="dataset.downloaded",
        entity_type="version",
        entity_id=version.id,
        dataset_id=dataset.id,
        version_id=version.id,
        details={"filename": version.original_filename},
    )

    filename = version.original_filename
    return StreamingResponse(
        storage.file_stream(version.storage_path),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.delete("/{dataset_id}", status_code=status.HTTP_200_OK)
def delete_dataset(
    dataset_id: str,
    db: Session = Depends(get_db),
):
    """Soft-delete dataset under safe retention rules (preserves artifact files and audit records)."""
    dataset = db.get(Dataset, dataset_id)
    if not dataset or dataset.is_deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Dataset not found.")

    dataset.is_deleted = True
    db.commit()

    log_audit(
        db,
        event_type="dataset.deleted",
        entity_type="dataset",
        entity_id=dataset.id,
        dataset_id=dataset.id,
        details={"name": dataset.name},
    )

    return {"message": f"Dataset '{dataset.name}' has been safely archived.", "id": dataset_id}
