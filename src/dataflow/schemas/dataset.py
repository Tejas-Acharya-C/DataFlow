"""Pydantic schemas for Datasets and Versions."""

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field


class DatasetBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None


class DatasetCreate(DatasetBase):
    pass


class DatasetVersionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True, protected_namespaces=())

    id: str
    dataset_id: str
    version_number: int
    storage_path: str
    original_filename: str
    file_size_bytes: int
    checksum: str
    row_count: int
    column_count: int
    schema_json: List[Dict[str, Any]]
    parent_version_id: Optional[str] = None
    creation_reason: str
    transformation_details: Optional[Dict[str, Any]] = None
    created_at: datetime


class DatasetResponse(DatasetBase):
    model_config = ConfigDict(from_attributes=True)

    id: str
    is_deleted: bool
    created_at: datetime
    updated_at: datetime
    latest_version: Optional[DatasetVersionResponse] = None
    version_count: int = 0


class DatasetDetailResponse(DatasetResponse):
    versions: List[DatasetVersionResponse] = []


class DatasetListResponse(BaseModel):
    items: List[DatasetResponse]
    total: int


class DatasetPreviewResponse(BaseModel):
    dataset_id: str
    version_id: str
    version_number: int
    columns: List[str]
    rows: List[Dict[str, Any]]
    total_preview_rows: int
    total_rows: int


class VersionCompareResponse(BaseModel):
    version_a_number: int
    version_b_number: int
    row_count_delta: int
    column_count_delta: int
    columns_added: List[str]
    columns_removed: List[str]
    columns_retained: List[str]
    schema_changes: List[Dict[str, Any]]
