"""Unit tests for CSV ingestion, storage safety, and checksums."""

import io

import pytest

from dataflow.services.ingestion import IngestionError, IngestionService
from dataflow.storage.local import PathTraversalError, StorageError


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


def test_header_only_csv(test_db_session, storage):
    csv_data = b"id,name,category\n"
    file_obj = io.BytesIO(csv_data)

    service = IngestionService(storage=storage)
    dataset, version = service.ingest_csv(
        db=test_db_session,
        file_obj=file_obj,
        filename="header_only.csv",
        dataset_name="Header Only Dataset",
    )

    assert version.row_count == 0
    assert version.column_count == 3
    assert [c["name"] for c in version.schema_json] == ["id", "name", "category"]


def test_unicode_and_special_characters(test_db_session, storage):
    csv_data = "id,name,city,notes\n1,René,München,✨Special™\n2,太郎,東京,日本語テスト\n".encode("utf-8")
    file_obj = io.BytesIO(csv_data)

    service = IngestionService(storage=storage)
    dataset, version = service.ingest_csv(
        db=test_db_session,
        file_obj=file_obj,
        filename="unicode.csv",
        dataset_name="Multilingual Dataset",
    )

    assert version.row_count == 2
    preview_cols, preview_rows, _ = storage.read_preview(version.storage_path)
    assert preview_rows[0]["name"] == "René"
    assert preview_rows[1]["city"] == "東京"


def test_null_values_in_csv(test_db_session, storage):
    csv_data = b"id,val_a,val_b\n1,,10.5\n2,text,\n3,,\n"
    file_obj = io.BytesIO(csv_data)

    service = IngestionService(storage=storage)
    _, version = service.ingest_csv(
        db=test_db_session,
        file_obj=file_obj,
        filename="nulls.csv",
    )

    assert version.row_count == 3
    null_cols = [c["name"] for c in version.schema_json if c["nullable"]]
    assert "val_a" in null_cols
    assert "val_b" in null_cols


def test_version_chaining_on_existing_dataset(test_db_session, storage):
    csv_v1 = b"id,name\n1,Alice\n"
    csv_v2 = b"id,name,role\n1,Alice,Admin\n2,Bob,User\n"

    service = IngestionService(storage=storage)
    dataset, v1 = service.ingest_csv(
        db=test_db_session,
        file_obj=io.BytesIO(csv_v1),
        filename="v1.csv",
        dataset_name="Versioning Test",
    )
    assert v1.version_number == 1

    # Ingest v2 on same dataset
    _, v2 = service.ingest_csv(
        db=test_db_session,
        file_obj=io.BytesIO(csv_v2),
        filename="v2.csv",
        dataset_id=dataset.id,
    )
    assert v2.version_number == 2
    assert v2.row_count == 2
    assert v2.column_count == 3


def test_upload_size_limit_rejection(test_db_session, storage):
    large_stream = io.BytesIO(b"a" * 500)
    # Save stream with 200 bytes limit
    with pytest.raises(StorageError, match="exceeds maximum allowed upload limit"):
        storage.save_stream(
            dataset_id="test_ds",
            version_id="test_ver",
            file_stream=large_stream,
            max_bytes=200,
        )


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
