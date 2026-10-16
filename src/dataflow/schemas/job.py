"""Pydantic schemas for ProcessingJobs and AuditEvents."""

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict


class JobResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    job_type: str
    dataset_id: Optional[str] = None
    version_id: Optional[str] = None
    status: str
    progress: int
    error_message: Optional[str] = None
    metadata_json: Optional[Dict[str, Any]] = None
    created_at: datetime
    finished_at: Optional[datetime] = None


class JobListResponse(BaseModel):
    items: List[JobResponse]
    total: int


class AuditEventResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    event_type: str
    entity_type: str
    entity_id: str
    dataset_id: Optional[str] = None
    version_id: Optional[str] = None
    outcome: str
    details_json: Optional[Dict[str, Any]] = None
    created_at: datetime


class AuditListResponse(BaseModel):
    items: List[AuditEventResponse]
    total: int
