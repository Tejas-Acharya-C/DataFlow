"""Schemas for external REST sources and incremental checkpoints."""

from datetime import datetime
from typing import Any, Dict, Optional

from pydantic import BaseModel, ConfigDict, Field


class RestSourceConfig(BaseModel):
    """Configuration for an external REST API extraction."""

    source_identifier: str = Field(
        ...,
        min_length=2,
        max_length=100,
        description="Unique identifier for the source system/feed",
    )
    url: str = Field(
        ...,
        description="Target REST API URL (http or https required)",
    )
    method: str = Field(default="GET", description="HTTP method (GET or POST)")
    params: Dict[str, Any] = Field(default_factory=dict, description="URL query parameters")
    headers: Dict[str, str] = Field(default_factory=dict, description="HTTP request headers")
    records_json_path: Optional[str] = Field(
        default=None,
        description="JSON key containing array of records, e.g. 'data' or 'results'",
    )
    cursor_column: Optional[str] = Field(
        default=None,
        description="Record field name containing the incremental cursor (e.g. 'updated_at' or 'id')",
    )
    cursor_param: Optional[str] = Field(
        default=None,
        description="Query parameter name to supply the previous watermark (e.g. 'since')",
    )
    pagination_type: Optional[str] = Field(
        default=None,
        description="Pagination strategy: None, 'page', or 'offset'",
    )
    page_param: str = Field(default="page", description="Query param for page number")
    limit_param: str = Field(default="limit", description="Query param for page limit")
    max_pages: int = Field(default=5, ge=1, le=50, description="Safety bound on extracted pages")
    page_size: int = Field(default=100, ge=1, le=1000, description="Records requested per page")
    dataset_id: Optional[str] = Field(
        default=None,
        description="Target existing dataset ID. If None, creates a new dataset.",
    )
    dataset_name: Optional[str] = Field(
        default=None,
        description="Name of dataset when creating a new dataset.",
    )


class CheckpointResponse(BaseModel):
    """Response schema for an ingestion checkpoint."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    source_identifier: str
    dataset_id: str
    cursor_column: str
    watermark_value: str
    records_extracted: int
    last_run_at: datetime
    created_at: datetime
    updated_at: datetime


class RestIngestionResponse(BaseModel):
    """Response returned upon completing a REST extraction and ingestion run."""

    job_id: str
    dataset_id: str
    version_id: str
    records_ingested: int
    watermark_value: Optional[str] = None
    pages_fetched: int
    status: str
