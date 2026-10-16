"""Audit logging and lightweight job status tracking service."""

import logging
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from sqlalchemy.orm import Session

from dataflow.models.job import AuditEvent, ProcessingJob

logger = logging.getLogger(__name__)


def log_audit(
    db: Session,
    event_type: str,
    entity_type: str,
    entity_id: str,
    outcome: str = "success",
    dataset_id: Optional[str] = None,
    version_id: Optional[str] = None,
    details: Optional[Dict[str, Any]] = None,
) -> AuditEvent:
    """Record an immutable audit log entry."""
    audit = AuditEvent(
        event_type=event_type,
        entity_type=entity_type,
        entity_id=entity_id,
        outcome=outcome,
        dataset_id=dataset_id,
        version_id=version_id,
        details_json=details or {},
    )
    db.add(audit)
    try:
        db.commit()
        db.refresh(audit)
    except Exception as exc:
        db.rollback()
        logger.error(f"Failed to record audit event: {exc}")
    return audit


def create_job(
    db: Session,
    job_type: str,
    dataset_id: Optional[str] = None,
    version_id: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> ProcessingJob:
    """Create a new tracked processing job."""
    job = ProcessingJob(
        job_type=job_type,
        dataset_id=dataset_id,
        version_id=version_id,
        status="running",
        progress=0,
        metadata_json=metadata or {},
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    return job


def complete_job(
    db: Session,
    job: ProcessingJob,
    status: str = "succeeded",
    error_message: Optional[str] = None,
    progress: int = 100,
) -> ProcessingJob:
    """Mark a processing job as succeeded or failed."""
    job.status = status
    job.progress = progress
    job.error_message = error_message
    job.finished_at = datetime.now(timezone.utc)
    db.add(job)
    db.commit()
    db.refresh(job)
    return job
