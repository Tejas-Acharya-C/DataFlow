"""Unit tests for row-level rejection persistence and quarantine partitioning."""

import io

from dataflow.models.contract import DataContract, ValidationRejection
from dataflow.services.ingestion import IngestionService
from dataflow.services.validation import ValidationService


def test_validation_quarantine_partitioning(test_db_session, storage):
    """Verify that validating mixed-quality data records row-level rejections and partitions data."""
    ingestion = IngestionService(storage=storage)
    val_service = ValidationService(storage=storage)

    # 4 rows: row 1 valid, row 2 null name (fails not_null), row 3 negative age (fails range), row 4 valid
    csv_data = (
        b"id,name,age\n"
        b"1,Alice,30\n"
        b"2,,25\n"
        b"3,Charlie,-5\n"
        b"4,Dana,40\n"
    )

    dataset, version = ingestion.ingest_csv(
        db=test_db_session,
        file_obj=io.BytesIO(csv_data),
        filename="mixed_users.csv",
    )

    contract = DataContract(
        name="User Validation Contract",
        rules_json={
            "required_columns": ["id", "name", "age"],
            "nullable_columns": {"name": False},
            "numeric_ranges": {"age": {"min": 0, "max": 120}},
        },
    )
    test_db_session.add(contract)
    test_db_session.commit()

    run = val_service.validate_version(
        db=test_db_session,
        version=version,
        contract=contract,
    )

    # Contract validation result checks
    assert run.status == "failed"
    assert run.accepted_rows == 2
    assert run.rejected_rows == 2
    assert run.quarantine_path is not None
    assert run.clean_path is not None

    # Check persisted row-level rejections
    rejections = test_db_session.query(ValidationRejection).filter_by(
        run_id=run.id
    ).order_by(ValidationRejection.row_number).all()

    assert len(rejections) == 2

    r1 = rejections[0]
    assert r1.row_number == 2
    assert any(reason.get("column") == "name" for reason in r1.failure_reasons)

    r2 = rejections[1]
    assert r2.row_number == 3
    assert any(reason.get("column") == "age" for reason in r2.failure_reasons)

    # Verify partitioned files exist in storage
    clean_bytes = storage.read_bytes(run.clean_path)
    quarantine_bytes = storage.read_bytes(run.quarantine_path)

    assert b"Alice" in clean_bytes
    assert b"Dana" in clean_bytes
    assert b"Charlie" not in clean_bytes
    assert b"Charlie" in quarantine_bytes
