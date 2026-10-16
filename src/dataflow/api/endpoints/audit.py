"""Audit event listing and querying endpoints."""

from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from dataflow.api.deps import get_db
from dataflow.models.job import AuditEvent
from dataflow.schemas.job import AuditEventResponse, AuditListResponse

router = APIRouter(prefix="/audit", tags=["Audit Logs"])


@router.get("", response_model=AuditListResponse)
def list_audit_events(
    event_type: Optional[str] = Query(None),
    outcome: Optional[str] = Query(None),
    dataset_id: Optional[str] = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    db: Session = Depends(get_db),
):
    """List paginated audit events with filtering."""
    stmt = select(AuditEvent)
    if event_type:
        stmt = stmt.where(AuditEvent.event_type == event_type)
    if outcome:
        stmt = stmt.where(AuditEvent.outcome == outcome)
    if dataset_id:
        stmt = stmt.where(AuditEvent.dataset_id == dataset_id)

    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    events = db.scalars(
        stmt.order_by(AuditEvent.created_at.desc()).offset(skip).limit(limit)
    ).all()

    return AuditListResponse(
        items=[AuditEventResponse.model_validate(e) for e in events],
        total=total,
    )
