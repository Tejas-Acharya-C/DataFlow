"""Unit tests for CSV ingestion, storage safety, and checksums."""

import io

import pytest

from dataflow.services.ingestion import IngestionError, IngestionService
from dataflow.storage.local import PathTraversalError


def test_valid_csv_ingestion(test_db_session, storage):
    csv_data = b"id,name,age\n1,Alice,30\n2,Bob,25\n3,Charlie,35\n"
    file_obj = io.BytesIO(csv_data)

    service = IngestionService(storage=storage)
    dataset, version = service.ingest_csv(
        db=test_db_session,
        file_obj=file_obj,
        filename="users.csv",
        dataset_name="Users Dataset",
    )

    assert dataset.name == "Users Dataset"
    assert version.version_number == 1
    assert version.row_count == 3
    assert version.column_count == 3
    assert len(version.checksum) == 64
    assert len(version.schema_json) == 3


def test_empty_csv_rejection(test_db_session, storage):
    empty_stream = io.BytesIO(b"")
    service = IngestionService(storage=storage)

    with pytest.raises(IngestionError, match="empty"):
        service.ingest_csv(
            db=test_db_session,
            file_obj=empty_stream,
            filename="empty.csv",
        )


def test_duplicate_headers_rejection(test_db_session, storage):
    dup_headers = b"col1,col2,col1\n1,2,3\n"
    file_obj = io.BytesIO(dup_headers)
    service = IngestionService(storage=storage)

    with pytest.raises(IngestionError, match="duplicate column headers"):
        service.ingest_csv(
            db=test_db_session,
            file_obj=file_obj,
            filename="dup.csv",
        )


def test_non_csv_rejection(test_db_session, storage):
    file_obj = io.BytesIO(b"some content")
    service = IngestionService(storage=storage)

    with pytest.raises(IngestionError, match="Only CSV files are accepted"):
        service.ingest_csv(
            db=test_db_session,
            file_obj=file_obj,
            filename="document.pdf",
        )


def test_path_traversal_prevention(storage):
    with pytest.raises(PathTraversalError):
        storage._resolve_safe_path("../../outside.csv")
