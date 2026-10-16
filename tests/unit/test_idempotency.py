"""Unit tests for idempotent ingestion and deduplication policies."""

import io

from dataflow.services.ingestion import IngestionService


def test_idempotent_upload_deduplication(test_db_session, storage):
    """Verify identical file uploads to the same dataset return existing version without duplicates."""
    service = IngestionService(storage=storage)

    csv_content = b"id,name,value\n1,Alpha,100\n2,Beta,200\n"

    # Initial upload
    dataset, v1 = service.ingest_csv(
        db=test_db_session,
        file_obj=io.BytesIO(csv_content),
        filename="test.csv",
        dataset_name="Idempotency Test",
    )
    assert v1.version_number == 1
    v1_id = v1.id

    # Second identical upload with deduplicate_identical=True (default)
    dataset, v2 = service.ingest_csv(
        db=test_db_session,
        file_obj=io.BytesIO(csv_content),
        filename="test.csv",
        dataset_id=dataset.id,
        deduplicate_identical=True,
    )
    # Must reuse version 1 and not create a duplicate version
    assert v2.id == v1_id
    assert v2.version_number == 1

    # Third upload with modified content
    modified_csv = b"id,name,value\n1,Alpha,100\n2,Beta,250\n"
    dataset, v3 = service.ingest_csv(
        db=test_db_session,
        file_obj=io.BytesIO(modified_csv),
        filename="test.csv",
        dataset_id=dataset.id,
        deduplicate_identical=True,
    )
    assert v3.version_number == 2
    assert v3.id != v1_id


def test_idempotent_override_policy(test_db_session, storage):
    """Verify that when deduplicate_identical=False, a new version is created even if content matches."""
    service = IngestionService(storage=storage)

    csv_content = b"id,code,status\n1,A1,active\n2,B2,pending\n"

    dataset, v1 = service.ingest_csv(
        db=test_db_session,
        file_obj=io.BytesIO(csv_content),
        filename="status.csv",
        dataset_name="Override Test",
    )
    assert v1.version_number == 1

    # Force new version with deduplicate_identical=False
    dataset, v2 = service.ingest_csv(
        db=test_db_session,
        file_obj=io.BytesIO(csv_content),
        filename="status.csv",
        dataset_id=dataset.id,
        deduplicate_identical=False,
    )
    assert v2.version_number == 2
    assert v2.id != v1.id
