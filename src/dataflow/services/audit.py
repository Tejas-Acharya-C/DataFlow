import logging
import os
import socket
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from dataflow.models.job import AuditEvent, ProcessingJob

logger = logging.getLogger(__name__)

WORKER_ID = f"{socket.gethostname()}:{os.getpid()}:{uuid.uuid4().hex[:6]}"


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
    max_attempts: int = 1,
    lease_seconds: int = 60,
    worker_id: Optional[str] = None,
) -> ProcessingJob:
    """Create a new tracked processing job with an active worker heartbeat lease."""
    now = datetime.now(timezone.utc)
    meta = dict(metadata or {})
    w_id = worker_id or WORKER_ID
    meta["worker_id"] = w_id
    meta["heartbeat_at"] = now.isoformat()
    meta["lease_expires_at"] = (now + timedelta(seconds=lease_seconds)).isoformat()
    meta["lease_seconds"] = lease_seconds

    job = ProcessingJob(
        job_type=job_type,
        dataset_id=dataset_id,
        version_id=version_id,
        status="running",
        progress=0,
        attempts=1,
        max_attempts=max_attempts,
        metadata_json=meta,
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    return job


def touch_job_heartbeat(
    db: Session,
    job: ProcessingJob,
    lease_seconds: Optional[int] = None,
) -> ProcessingJob:
    """Refresh the heartbeat timestamp and extend the lease on an actively running job."""
    now = datetime.now(timezone.utc)
    meta = dict(job.metadata_json or {})
    duration = lease_seconds or meta.get("lease_seconds", 60)
    meta["heartbeat_at"] = now.isoformat()
    meta["lease_expires_at"] = (now + timedelta(seconds=duration)).isoformat()
    job.metadata_json = meta
    db.add(job)
    db.commit()
    db.refresh(job)
    return job


def is_job_lease_expired(
    job: ProcessingJob,
    now: Optional[datetime] = None,
    default_lease_seconds: int = 60,
) -> bool:
    """Check whether a job's lease has expired and it is safe to reconcile as stale."""
    if job.status not in ("running", "retried"):
        return False

    current_time = now or datetime.now(timezone.utc)
    meta = job.metadata_json or {}

    lease_str = meta.get("lease_expires_at")
    if lease_str:
        try:
            expires_at = datetime.fromisoformat(lease_str)
            if expires_at.tzinfo is None:
                expires_at = expires_at.replace(tzinfo=timezone.utc)
            return current_time > expires_at
        except (ValueError, TypeError):
            pass

    heartbeat_str = meta.get("heartbeat_at")
    if heartbeat_str:
        try:
            last_hb = datetime.fromisoformat(heartbeat_str)
            if last_hb.tzinfo is None:
                last_hb = last_hb.replace(tzinfo=timezone.utc)
            duration = meta.get("lease_seconds", default_lease_seconds)
            return (current_time - last_hb).total_seconds() > duration
        except (ValueError, TypeError):
            pass

    # Fallback to created_at if no heartbeat metadata exists
    created = job.created_at
    if created:
        if created.tzinfo is None:
            created = created.replace(tzinfo=timezone.utc)
        return (current_time - created).total_seconds() > default_lease_seconds

    return True


def update_job_attempt(
    db: Session,
    job: ProcessingJob,
    attempt: int,
    error_message: Optional[str] = None,
    error_category: Optional[str] = None,
) -> ProcessingJob:
    """Record a retry attempt on a running job."""
    job.attempts = attempt
    job.status = "retried"
    if error_message:
        job.error_message = error_message
    if error_category:
        job.error_category = error_category
    db.add(job)
    db.commit()
    db.refresh(job)
    return job


def complete_job(
    db: Session,
    job: ProcessingJob,
    status: str = "succeeded",
    error_message: Optional[str] = None,
    error_category: Optional[str] = None,
    progress: int = 100,
    metadata: Optional[Dict[str, Any]] = None,
    metrics: Optional[Dict[str, Any]] = None,
) -> ProcessingJob:
    """Mark a processing job as succeeded, failed, or interrupted, calculating duration."""
    now = datetime.now(timezone.utc)
    job.status = status
    job.progress = progress
    job.error_message = error_message
    if error_category:
        job.error_category = error_category
    if metadata:
        meta = dict(job.metadata_json or {})
        meta.update(metadata)
        job.metadata_json = meta
    if metrics:
        meta = dict(job.metadata_json or {})
        meta["metrics"] = metrics
        job.metadata_json = meta
    job.finished_at = now
    if job.created_at:
        # Calculate duration in milliseconds (support offset-naive SQLite datetimes)
        created = job.created_at
        if created.tzinfo is None:
            created = created.replace(tzinfo=timezone.utc)
        delta = now - created
        job.duration_ms = max(0, int(delta.total_seconds() * 1000))
    db.add(job)
    db.commit()
    db.refresh(job)
    return job


def reconcile_stale_jobs(
    db: Session,
    stale_threshold_seconds: int = 60,
) -> int:
    """
    Recover from crashed workers by transitioning genuinely stale jobs to 'interrupted'.
    Jobs with an active unexpired heartbeat lease on other workers are preserved.
    """
    candidate_jobs = db.scalars(
        select(ProcessingJob).where(ProcessingJob.status.in_(["running", "retried"]))
    ).all()

    now = datetime.now(timezone.utc)
    count = 0
    for job in candidate_jobs:
        if not is_job_lease_expired(job, now=now, default_lease_seconds=stale_threshold_seconds):
            # Job is actively running on another worker with a valid lease; do NOT touch it
            worker = job.metadata_json.get("worker_id", "unknown") if job.metadata_json else "unknown"
            logger.debug(f"Preserving active job {job.id} held by worker {worker}")
            continue

        job.status = "interrupted"
        last_hb = job.metadata_json.get("heartbeat_at") if job.metadata_json else None
        job.error_message = (
            f"Job worker lease expired without heartbeat (last heartbeat: {last_hb}). Reconciled as stale."
        )
        job.error_category = "process_crash"
        job.finished_at = now
        if job.created_at:
            created = job.created_at
            if created.tzinfo is None:
                created = created.replace(tzinfo=timezone.utc)
            job.duration_ms = max(0, int((now - created).total_seconds() * 1000))
        db.add(job)
        count += 1

    if count > 0:
        db.commit()
        logger.info(f"Reconciled {count} stale running jobs to 'interrupted' status.")
    return count


class AuditService:
    """Service wrapper for audit logging and job lifecycle management."""

    log_audit = staticmethod(log_audit)
    create_job = staticmethod(create_job)
    update_job_attempt = staticmethod(update_job_attempt)
    touch_heartbeat = staticmethod(touch_job_heartbeat)
    is_job_lease_expired = staticmethod(is_job_lease_expired)
    complete_job = staticmethod(complete_job)
    reconcile_stale_jobs = staticmethod(reconcile_stale_jobs)
