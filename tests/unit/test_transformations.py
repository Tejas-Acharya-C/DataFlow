"""Unit tests for safe dataframe transformations and immutable versioning."""

import io

import pytest

from dataflow.services.ingestion import IngestionService
from dataflow.services.transformation import TransformationError, TransformationService


def test_transformations_execution(test_db_session, storage):
    csv_data = (
        b"id,name,val\n"
        b"1, Alice ,10\n"
        b"2, Bob ,20\n"
        b"2, Bob ,20\n"
        b"3, Charlie ,\n"
    )
    ingestion = IngestionService(storage=storage)
    dataset, v1 = ingestion.ingest_csv(
        db=test_db_session,
        file_obj=io.BytesIO(csv_data),
        filename="trans.csv",
    )

    service = TransformationService(storage=storage)
    ops = [
        {"op": "remove_duplicates"},
        {"op": "trim_strings", "columns": ["name"]},
        {"op": "fill_missing", "columns": ["val"], "value": 0},
        {"op": "filter_rows", "column": "id", "operator": "gte", "value": 2},
        {"op": "rename_columns", "mapping": {"val": "score"}},
    ]

    # Test preview
    preview = service.preview_transformation(version=v1, operations=ops)
    assert preview["original_row_count"] == 4
    assert preview["new_row_count"] == 2
    assert "score" in preview["columns"]
    assert "val" not in preview["columns"]

    # Test apply
    v2 = service.apply_transformation(
        db=test_db_session,
        version=v1,
        operations=ops,
        reason="Deduplicate, clean, and rename",
    )

    assert v2.version_number == 2
    assert v2.parent_version_id == v1.id
    assert v2.row_count == 2
    assert v2.column_count == 3


def test_empty_filter_result(test_db_session, storage):
    csv_data = b"id,val\n1,10\n2,20\n"
    ingestion = IngestionService(storage=storage)
    _, v1 = ingestion.ingest_csv(
        db=test_db_session,
        file_obj=io.BytesIO(csv_data),
        filename="filter.csv",
    )

    service = TransformationService(storage=storage)
    ops = [{"op": "filter_rows", "column": "id", "operator": "gt", "value": 999}]
    preview = service.preview_transformation(version=v1, operations=ops)
    assert preview["new_row_count"] == 0
    assert len(preview["preview_rows"]) == 0


def test_invalid_column_transformation_error(test_db_session, storage):
    csv_data = b"id,val\n1,10\n"
    ingestion = IngestionService(storage=storage)
    _, v1 = ingestion.ingest_csv(
        db=test_db_session,
        file_obj=io.BytesIO(csv_data),
        filename="err.csv",
    )

    service = TransformationService(storage=storage)
    ops = [{"op": "filter_rows", "column": "non_existent", "operator": "eq", "value": 1}]

    with pytest.raises(TransformationError, match="Column 'non_existent' not found"):
        service.preview_transformation(version=v1, operations=ops)


def test_date_conversion_transformation(test_db_session, storage):
    csv_data = b"id,created_at\n1,2026/10/16\n2,2026/05/01\n"
    ingestion = IngestionService(storage=storage)
    _, v1 = ingestion.ingest_csv(
        db=test_db_session,
        file_obj=io.BytesIO(csv_data),
        filename="dates.csv",
    )

    service = TransformationService(storage=storage)
    ops = [{"op": "convert_dates", "column": "created_at", "input_format": "%Y/%m/%d", "output_format": "%Y-%m-%d"}]
    preview = service.preview_transformation(version=v1, operations=ops)
    assert preview["preview_rows"][0]["created_at"] == "2026-10-16"
    assert preview["preview_rows"][1]["created_at"] == "2026-05-01"
