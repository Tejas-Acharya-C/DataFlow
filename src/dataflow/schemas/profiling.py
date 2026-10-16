"""Pydantic schemas for Data Profiling."""

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict


class ColumnProfile(BaseModel):
    name: str
    detected_type: str
    total_count: int
    null_count: int
    null_percentage: float
    distinct_count: int
    uniqueness_percentage: float
    is_constant: bool
    numeric_min: Optional[float] = None
    numeric_max: Optional[float] = None
    numeric_mean: Optional[float] = None
    numeric_median: Optional[float] = None
    numeric_std: Optional[float] = None
    string_min_length: Optional[int] = None
    string_max_length: Optional[int] = None
    string_avg_length: Optional[float] = None
    top_values: List[Dict[str, Any]] = []
    min_date: Optional[str] = None
    max_date: Optional[str] = None


class DatasetProfileSummary(BaseModel):
    row_count: int
    column_count: int
    duplicate_rows_count: int
    duplicate_rows_percentage: float
    total_cells: int
    total_missing_cells: int
    missing_cells_percentage: float


class ProfilingResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    dataset_id: str
    version_id: str
    summary_json: Dict[str, Any]
    columns_json: Dict[str, Any]
    created_at: datetime
