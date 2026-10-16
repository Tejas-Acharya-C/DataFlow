"""Unit tests for data contract validation execution."""

import io

from dataflow.models.contract import DataContract
from dataflow.services.ingestion import IngestionService
from dataflow.services.validation import ValidationService


def test_contract_validation_success_and_failures(test_db_session, storage):
    csv_data = (
        b"user_id,email,age,status\n"
        b"1,user1@test.com,25,active\n"
        b"2,user2@test.com,17,pending\n"
        b"3,user1@test.com,40,invalid_status\n"  # duplicate email, invalid status
    )
    ingestion = IngestionService(storage=storage)
    dataset, version = ingestion.ingest_csv(
        db=test_db_session,
        file_obj=io.BytesIO(csv_data),
        filename="users_validation.csv",
    )

    contract = DataContract(
        name="User Validation Contract",
        rules_json={
            "required_columns": ["user_id", "email", "age", "status", "missing_col"],
            "unique_columns": ["email"],
            "numeric_ranges": {"age": {"min": 18, "max": 120}},
            "allowed_values": {"status": ["active", "pending", "suspended"]},
            "nullable_columns": {"email": False},
        },
    )
    test_db_session.add(contract)
    test_db_session.commit()

    val_service = ValidationService(storage=storage)
    run = val_service.validate_version(db=test_db_session, version=version, contract=contract)

    assert run.status == "failed"
    assert run.failed_count > 0

    checks = {c["name"]: c for c in run.results_json["checks"]}
    assert checks["required_column:missing_col"]["status"] == "failed"
    assert checks["required_column:user_id"]["status"] == "passed"
    assert checks["uniqueness:email"]["status"] == "failed"
    assert checks["range_check:age"]["status"] == "failed"
    assert checks["allowed_values:status"]["status"] == "failed"
