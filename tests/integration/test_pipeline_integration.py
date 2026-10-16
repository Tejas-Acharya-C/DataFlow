"""End-to-end integration test of the DataFlow platform lifecycle."""

import io

from dataflow.models.contract import DataContract
from dataflow.services.ingestion import IngestionService
from dataflow.services.lineage import compare_versions
from dataflow.services.profiling import ProfilingService
from dataflow.services.quality import QualityService
from dataflow.services.transformation import TransformationService
from dataflow.services.validation import ValidationService


def test_full_dataflow_lifecycle(test_db_session, storage):
    # 1. Ingestion
    raw_csv = (
        b"id,customer_name,spend,tier\n"
        b"1, Acme Corp ,500.00,Gold\n"
        b"2, Globex ,120.50,Silver\n"
        b"3, Initech ,45.00,Bronze\n"
    )
    ingestion = IngestionService(storage=storage)
    dataset, v1 = ingestion.ingest_csv(
        db=test_db_session,
        file_obj=io.BytesIO(raw_csv),
        filename="customers.csv",
        dataset_name="Enterprise Customers",
    )
    assert dataset.id is not None
    assert v1.version_number == 1
    assert v1.row_count == 3

    # 2. Profiling
    profiler = ProfilingService(storage=storage)
    prof = profiler.profile_version(db=test_db_session, version=v1)
    assert prof.summary_json["row_count"] == 3
    assert prof.columns_json["spend"]["numeric_min"] == 45.0
    assert prof.columns_json["spend"]["numeric_max"] == 500.0

    # 3. Quality evaluation
    quality_service = QualityService(storage=storage)
    quality = quality_service.evaluate_version(db=test_db_session, version=v1)
    assert quality.score > 0
    assert quality.status in ["excellent", "good", "fair", "poor"]

    # 4. Contract validation
    contract = DataContract(
        name="Customer SLA Contract",
        rules_json={
            "required_columns": ["id", "customer_name", "spend", "tier"],
            "allowed_values": {"tier": ["Gold", "Silver", "Bronze"]},
            "numeric_ranges": {"spend": {"min": 0, "max": 10000}},
        },
    )
    test_db_session.add(contract)
    test_db_session.commit()

    val_service = ValidationService(storage=storage)
    run = val_service.validate_version(db=test_db_session, version=v1, contract=contract)
    assert run.status == "passed"
    assert run.failed_count == 0

    # 5. Safe transformation -> creates v2
    transform_service = TransformationService(storage=storage)
    ops = [
        {"op": "trim_strings", "columns": ["customer_name"]},
        {"op": "rename_columns", "mapping": {"spend": "total_spend_usd"}},
    ]
    v2 = transform_service.apply_transformation(
        db=test_db_session,
        version=v1,
        operations=ops,
        reason="Clean customer names and rename spend column",
    )
    assert v2.version_number == 2
    assert v2.parent_version_id == v1.id

    # 6. Version comparison
    diff = compare_versions(v1, v2)
    assert "total_spend_usd" in diff["columns_added"]
    assert "spend" in diff["columns_removed"]
    assert diff["row_count_delta"] == 0
