"""Pydantic schemas for Data Quality Evaluation."""

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict


class QualityCheckItem(BaseModel):
    name: str
    category: str
    status: str  # passed, failed, warning
    score_impact: float  # points deducted
    message: str
    affected_column: Optional[str] = None
    failure_rate: float = 0.0
    recommendation: Optional[str] = None


class QualityEvaluationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    dataset_id: str
    version_id: str
    score: float
    status: str
    summary: str
    checks_json: Dict[str, Any]
    recommendations_json: List[str]
    created_at: datetime
