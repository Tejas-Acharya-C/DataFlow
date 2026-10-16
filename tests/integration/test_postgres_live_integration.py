import io
import os
import uuid

import pytest
from sqlalchemy import create_engine, delete, select, text
from sqlalchemy.orm import sessionmaker

from dataflow.config import get_settings
from dataflow.db.base import Base
from dataflow.models.contract import DataContract, ValidationRun
from dataflow.models.dataset import Dataset
from dataflow.models.profiling import ProfilingResult, QualityResult
from dataflow.services.ingestion import IngestionService
from dataflow.services.lineage import compare_versions
from dataflow.services.profiling import ProfilingService
from dataflow.services.quality import QualityService
from dataflow.services.transformation import TransformationService
from dataflow.services.validation import ValidationService


def get_test_pg_url() -> str:
    """Resolve PostgreSQL connection URL for integration testing."""
    if os.environ.get("TEST_DATABASE_URL"):
        return os.environ["TEST_DATABASE_URL"]
    env_url = os.environ.get("DATAFLOW_DATABASE_URL", "")
    if "postgres" in env_url:
        return env_url
    settings_url = get_settings().get_effective_database_url()
    if "postgres" in settings_url:
        return settings_url
    return "postgresql+psycopg://dataflow:dataflow_secret_password@localhost:55432/dataflow"


@pytest.fixture(scope="module")
def pg_session():
    """Connect to live PostgreSQL container or fail in CI / skip if locally unavailable."""
    pg_url = get_test_pg_url()
    require_pg = bool(os.environ.get("REQUIRE_POSTGRES_TEST") or os.environ.get("CI"))

    try:
        engine = create_engine(pg_url, pool_pre_ping=True)
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
    except Exception as exc:
        if require_pg:
            pytest.fail(
                f"PostgreSQL integration test is required in CI, but database connection failed at {pg_url}: {exc}"
            )
        pytest.skip(
            f"Live PostgreSQL not reachable at {pg_url}. Start with `docker compose up -d` to run live integration tests: {exc}"
        )

    # Ensure schema is ready
    Base.metadata.create_all(bind=engine)

    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = SessionLocal()
    yield session
    session.close()


def test_live_postgres_end_to_end_pipeline(pg_session, storage):
    """Verify full dataset ingestion, validation, profiling, and transformation on real PostgreSQL."""
    test_ds_name = f"PG Live Test Dataset {uuid.uuid4().hex[:8]}"
    raw_csv = (
        b"id,customer,amount,region,status\n"
        b"1,Acme Corp,150.50,EMEA,active\n"
        b"2,Globex,320.00,AMER,active\n"
        b"3,Initech,45.25,APAC,pending\n"
        b"4,Soylent,0.00,EMEA,inactive\n"
    )

    # 1. Ingest into PostgreSQL
    ingestion = IngestionService(storage=storage)
    dataset, v1 = ingestion.ingest_csv(
        db=pg_session,
        file_obj=io.BytesIO(raw_csv),
        filename="pg_test_orders.csv",
        dataset_name=test_ds_name,
    )
    assert dataset.id is not None
    assert v1.version_number == 1
    assert v1.row_count == 4
    assert v1.column_count == 5

    # Verify query directly from PostgreSQL
    db_ds = pg_session.scalar(select(Dataset).where(Dataset.id == dataset.id))
    assert db_ds is not None
    assert db_ds.name == test_ds_name

    # 2. Statistical Profiling
    profiler = ProfilingService(storage=storage)
    prof = profiler.profile_version(db=pg_session, version=v1)
    assert prof.summary_json["row_count"] == 4
    assert prof.columns_json["amount"]["numeric_min"] == 0.0
    assert prof.columns_json["amount"]["numeric_max"] == 320.0

    # 3. Deterministic Quality Scoring
    quality_service = QualityService(storage=storage)
    qual = quality_service.evaluate_version(db=pg_session, version=v1)
    assert qual.score == 100.0
    assert qual.status == "excellent"

    # 4. Data Contract Creation & Validation
    contract = DataContract(
        name=f"PG SLA Contract {uuid.uuid4().hex[:8]}",
        rules_json={
            "required_columns": ["id", "customer", "amount", "region", "status"],
            "allowed_values": {"status": ["active", "pending", "inactive"]},
            "numeric_ranges": {"amount": {"min": 0, "max": 10000}},
            "nullable_columns": {"customer": False},
        },
    )
    pg_session.add(contract)
    pg_session.commit()

    val_service = ValidationService(storage=storage)
    run = val_service.validate_version(db=pg_session, version=v1, contract=contract)
    assert run.status == "passed"
    assert run.failed_count == 0

    # 5. Transformations -> Immutable Version 2
    transform_service = TransformationService(storage=storage)
    ops = [
        {"op": "filter_rows", "column": "status", "operator": "eq", "value": "active"},
        {"op": "rename_columns", "mapping": {"amount": "spend_usd"}},
    ]
    v2 = transform_service.apply_transformation(
        db=pg_session,
        version=v1,
        operations=ops,
        reason="Filter active accounts and rename amount column",
    )
    assert v2.version_number == 2
    assert v2.parent_version_id == v1.id
    assert v2.row_count == 2
    assert v2.column_count == 5

    # 6. Version Diff & Lineage
    diff = compare_versions(v1, v2)
    assert "spend_usd" in diff["columns_added"]
    assert "amount" in diff["columns_removed"]
    assert diff["row_count_delta"] == -2

    # Cleanup test records
    pg_session.execute(delete(ValidationRun).where(ValidationRun.contract_id == contract.id))
    pg_session.execute(delete(ProfilingResult).where(ProfilingResult.dataset_id == dataset.id))
    pg_session.execute(delete(QualityResult).where(QualityResult.dataset_id == dataset.id))
    pg_session.execute(delete(Dataset).where(Dataset.id == dataset.id))
    pg_session.execute(delete(DataContract).where(DataContract.id == contract.id))
    pg_session.commit()
