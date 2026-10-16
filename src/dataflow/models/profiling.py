"""ProfilingResult and QualityResult models."""

import uuid
from datetime import datetime, timezone
from typing import Any, Dict

from sqlalchemy import (
    JSON,
    DateTime,
    Float,
    ForeignKey,
    String,
)
from sqlalchemy.orm import Mapped, mapped_column

from dataflow.db.base import Base


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class ProfilingResult(Base):
    """Profiling metrics snapshot for a dataset version."""

    __tablename__ = "profiling_results"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    dataset_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("datasets.id", ondelete="CASCADE"), nullable=False, index=True
    )
    version_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("dataset_versions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    summary_json: Mapped[Dict[str, Any]] = mapped_column(JSON, nullable=False)
    columns_json: Mapped[Dict[str, Any]] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )


class QualityResult(Base):
    """Data quality evaluation result with deterministic score and breakdown."""

    __tablename__ = "quality_results"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    dataset_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("datasets.id", ondelete="CASCADE"), nullable=False, index=True
    )
    version_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("dataset_versions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    score: Mapped[float] = mapped_column(Float, nullable=False)  # 0.0 to 100.0
    status: Mapped[str] = mapped_column(String(50), nullable=False)  # excellent, good, fair, poor
    summary: Mapped[str] = mapped_column(String(500), nullable=False)
    checks_json: Mapped[Dict[str, Any]] = mapped_column(JSON, nullable=False)
    recommendations_json: Mapped[list] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )
