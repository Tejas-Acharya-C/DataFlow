"""DataContract and ValidationRun models."""

import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy import (
    JSON,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from dataflow.db.base import Base


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class DataContract(Base):
    """Reusable data contract defining schema expectations and validation rules."""

    __tablename__ = "data_contracts"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False, unique=True, index=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    rules_json: Mapped[Dict[str, Any]] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False
    )

    validation_runs: Mapped[List["ValidationRun"]] = relationship(
        "ValidationRun", back_populates="contract", cascade="all, delete-orphan"
    )


class ValidationRun(Base):
    """Execution run of a data contract on a specific dataset version."""

    __tablename__ = "validation_runs"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    dataset_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("datasets.id", ondelete="CASCADE"), nullable=False, index=True
    )
    version_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("dataset_versions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    contract_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("data_contracts.id", ondelete="CASCADE"), nullable=False, index=True
    )
    status: Mapped[str] = mapped_column(String(50), nullable=False)  # passed, failed, warning
    passed_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    failed_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    accepted_rows: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    rejected_rows: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    quarantine_path: Mapped[Optional[str]] = mapped_column(String(1024), nullable=True)
    clean_path: Mapped[Optional[str]] = mapped_column(String(1024), nullable=True)
    results_json: Mapped[Dict[str, Any]] = mapped_column(JSON, nullable=False)
    executed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )

    contract: Mapped["DataContract"] = relationship("DataContract", back_populates="validation_runs")
    rejections: Mapped[List["ValidationRejection"]] = relationship(
        "ValidationRejection", back_populates="validation_run", cascade="all, delete-orphan"
    )


class ValidationRejection(Base):
    """Stores row-level validation failure details for auditing and diagnosis."""

    __tablename__ = "validation_rejections"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    run_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("validation_runs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    dataset_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("datasets.id", ondelete="CASCADE"), nullable=False, index=True
    )
    version_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("dataset_versions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    row_number: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    raw_data: Mapped[Dict[str, Any]] = mapped_column(JSON, nullable=False)
    failure_reasons: Mapped[List[Dict[str, Any]]] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )

    validation_run: Mapped["ValidationRun"] = relationship(
        "ValidationRun", back_populates="rejections"
    )
