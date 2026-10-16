"""Pydantic schemas for Data Transformations."""

from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field


class RenameColumnsOp(BaseModel):
    op: Literal["rename_columns"] = "rename_columns"
    mapping: Dict[str, str] = Field(..., description="Mapping of old column name to new column name")


class SelectColumnsOp(BaseModel):
    op: Literal["select_columns"] = "select_columns"
    columns: List[str]


class DropColumnsOp(BaseModel):
    op: Literal["drop_columns"] = "drop_columns"
    columns: List[str]


class RemoveDuplicatesOp(BaseModel):
    op: Literal["remove_duplicates"] = "remove_duplicates"
    subset: Optional[List[str]] = None
    keep: Literal["first", "last"] = "first"


class FillMissingOp(BaseModel):
    op: Literal["fill_missing"] = "fill_missing"
    columns: List[str]
    strategy: Literal["constant", "mean", "median", "mode", "forward_fill", "backward_fill"] = "constant"
    value: Optional[Any] = None


class CastColumnsOp(BaseModel):
    op: Literal["cast_columns"] = "cast_columns"
    conversions: Dict[str, Literal["int", "float", "str", "bool", "datetime"]]


class FilterRowsOp(BaseModel):
    op: Literal["filter_rows"] = "filter_rows"
    column: str
    operator: Literal["eq", "neq", "gt", "gte", "lt", "lte", "in", "not_in", "is_null", "is_not_null", "contains"]
    value: Optional[Any] = None


class SortRowsOp(BaseModel):
    op: Literal["sort_rows"] = "sort_rows"
    by: List[str]
    ascending: List[bool] = [True]


class TrimStringsOp(BaseModel):
    op: Literal["trim_strings"] = "trim_strings"
    columns: Optional[List[str]] = None
    lowercase: bool = False
    uppercase: bool = False


class ConvertDatesOp(BaseModel):
    op: Literal["convert_dates"] = "convert_dates"
    column: str
    input_format: Optional[str] = None
    output_format: str = "%Y-%m-%d"


TransformationStep = (
    RenameColumnsOp
    | SelectColumnsOp
    | DropColumnsOp
    | RemoveDuplicatesOp
    | FillMissingOp
    | CastColumnsOp
    | FilterRowsOp
    | SortRowsOp
    | TrimStringsOp
    | ConvertDatesOp
)


class TransformationRequest(BaseModel):
    dataset_id: str
    version_id: str
    operations: List[Dict[str, Any]] = Field(..., description="Ordered list of transformation operations")
    reason: Optional[str] = "Data transformation pipeline"


class TransformationPreviewResponse(BaseModel):
    dataset_id: str
    version_id: str
    original_row_count: int
    original_column_count: int
    new_row_count: int
    new_column_count: int
    columns: List[str]
    preview_rows: List[Dict[str, Any]]
    operations_applied: int


class TransformationApplyResponse(BaseModel):
    dataset_id: str
    new_version_id: str
    version_number: int
    parent_version_id: str
    row_count: int
    column_count: int
    checksum: str
    created_at: str
