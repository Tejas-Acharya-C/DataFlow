"""ProcessingJob and AuditEvent models."""

import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from sqlalchemy import (
    JSON,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column

from dataflow.db.base import Base


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class ProcessingJob(Base):
    """Tracks background or synchronous operation execution and state."""

    __tablename__ = "processing_jobs"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    job_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    dataset_id: Mapped[Optional[str]] = mapped_column(
        String(36), ForeignKey("datasets.id", ondelete="SET NULL"), nullable=True, index=True
    )
    version_id: Mapped[Optional[str]] = mapped_column(
        String(36), ForeignKey("dataset_versions.id", ondelete="SET NULL"), nullable=True
    )
    status: Mapped[str] = mapped_column(
        String(50), nullable=False, default="pending", index=True
    )  # pending, running, succeeded, failed
    progress: Mapped[int] = mapped_column(Integer, default=0, nullable=False)  # 0 to 100
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    metadata_json: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False, index=True
    )
    finished_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )


class AuditEvent(Base):
    """Immutable audit event logging actions, data mutations, and outcomes."""

    __tablename__ = "audit_events"
    __table_args__ = (
        Index("ix_audit_event_type_outcome", "event_type", "outcome"),
    )

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    event_type: Mapped[str] = mapped_column(
        String(50), nullable=False, index=True
    )  # dataset.uploaded, dataset.transformed, validation.executed, etc.
    entity_type: Mapped[str] = mapped_column(String(50), nullable=False)  # dataset, version, contract
    entity_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    dataset_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True, index=True)
    version_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    outcome: Mapped[str] = mapped_column(
        String(50), nullable=False, default="success"
    )  # success, failure, warning
    details_json: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False, index=True
    )
