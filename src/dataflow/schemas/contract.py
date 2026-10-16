"""Pydantic schemas for Data Contracts and Validations."""

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field


class ContractRules(BaseModel):
    """Specification of contract validation rules."""
    required_columns: Optional[List[str]] = Field(default_factory=list)
    column_types: Optional[Dict[str, str]] = Field(default_factory=dict)  # "int", "float", "str", "bool", "datetime"
    nullable_columns: Optional[Dict[str, bool]] = Field(default_factory=dict)
    unique_columns: Optional[List[str]] = Field(default_factory=list)
    allowed_values: Optional[Dict[str, List[Any]]] = Field(default_factory=dict)
    numeric_ranges: Optional[Dict[str, Dict[str, Optional[float]]]] = Field(default_factory=dict)  # {"min": 0, "max": 100}
    string_lengths: Optional[Dict[str, Dict[str, Optional[int]]]] = Field(default_factory=dict)  # {"min_len": 1, "max_len": 50}
    date_formats: Optional[Dict[str, str]] = Field(default_factory=dict)  # {"created_date": "%Y-%m-%d"}
    min_rows: Optional[int] = None
    max_rows: Optional[int] = None
    disallow_schema_drift: Optional[bool] = False  # If True, extra uncontracted columns fail validation


class ContractCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    rules: ContractRules


class ContractUpdate(BaseModel):
    description: Optional[str] = None
    rules: Optional[ContractRules] = None


class ContractResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    description: Optional[str] = None
    version: int
    rules_json: Dict[str, Any]
    created_at: datetime
    updated_at: datetime


class CheckResult(BaseModel):
    name: str
    category: str
    status: str  # passed, failed, warning
    severity: str  # error, warning
    message: str
    affected_column: Optional[str] = None
    failed_count: int = 0
    failure_rate: float = 0.0
    sample_failures: List[Any] = Field(default_factory=list)
    recommendation: Optional[str] = None


class ValidationRunResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    dataset_id: str
    version_id: str
    contract_id: str
    status: str  # passed, failed, warning
    passed_count: int
    failed_count: int
    results_json: Dict[str, Any]
    executed_at: datetime
