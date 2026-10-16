"""Unit tests for safe dataframe transformations and immutable versioning."""

import io

from dataflow.services.ingestion import IngestionService
from dataflow.services.transformation import TransformationService


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
