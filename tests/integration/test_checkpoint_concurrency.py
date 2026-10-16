"""Live PostgreSQL concurrency tests for incremental ingestion checkpoints."""

import concurrent.futures
import io
import os
import time
import uuid

import pytest
from sqlalchemy import create_engine, select, text
from sqlalchemy.orm import sessionmaker

from dataflow.config import get_settings
from dataflow.db.base import Base
from dataflow.models.dataset import DatasetVersion, IngestionCheckpoint
from dataflow.schemas.source import RestSourceConfig
from dataflow.services.ingestion import IngestionService
from dataflow.services.rest_ingestion import RestIngestionService


def get_pg_engine():
    """Resolve live PostgreSQL engine or return None if unavailable."""
    url = os.environ.get("TEST_DATABASE_URL")
    if not url:
        settings_url = get_settings().get_effective_database_url()
        url = settings_url if "postgres" in settings_url else "postgresql+psycopg://dataflow:dataflow_secret_password@localhost:55432/dataflow"

    try:
        engine = create_engine(url, pool_pre_ping=True, pool_size=10)
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return engine
    except Exception:
        return None


@pytest.fixture(scope="module")
def pg_engine():
    engine = get_pg_engine()
    if engine is None:
        if os.environ.get("REQUIRE_POSTGRES_TEST") or os.environ.get("CI"):
            pytest.fail("Live PostgreSQL is required but unreachable on port 55432.")
        pytest.skip("Live PostgreSQL not reachable; skipping concurrency tests.")

    Base.metadata.create_all(bind=engine)
    yield engine
    engine.dispose()


def test_concurrent_checkpoint_creation_and_watermark_advancement(pg_engine, storage):
    """Verify concurrent ingestion runs on PostgreSQL serialize safely without duplicate versions,

    lost watermarks, or checkpoint constraint collisions.
    """
    SessionLocal = sessionmaker(bind=pg_engine, autocommit=False, autoflush=False)
    setup_db = SessionLocal()

    # 1. Create a parent dataset
    ingestion = IngestionService(storage=storage)
    dataset, v1 = ingestion.ingest_csv(
        db=setup_db,
        file_obj=io.BytesIO(b"id,val\n1,alpha\n"),
        filename="init.csv",
        dataset_name=f"Concurrent Checkpoint Test {uuid.uuid4().hex[:6]}",
    )
    dataset_id = dataset.id
    source_id = f"stream_{uuid.uuid4().hex[:6]}"
    setup_db.close()

    # 2. Prepare two worker ingestion calls with incremental data batches
    # Worker 1 has records with id 101, 102
    # Worker 2 has records with id 103, 104
    def worker_task(worker_id: int):
        thread_db = SessionLocal()
        try:
            thread_service = RestIngestionService(ingestion_service=IngestionService(storage=storage))

            def mock_page(client, url, params, headers, allow_private_hosts=False):
                # Add a tiny artificial sleep to ensure transactions overlap in execution window
                time.sleep(0.05)
                if worker_id == 1:
                    return {
                        "results": [
                            {"id": 101, "val": "worker1_a"},
                            {"id": 102, "val": "worker1_b"},
                        ]
                    }
                else:
                    return {
                        "results": [
                            {"id": 103, "val": "worker2_a"},
                            {"id": 104, "val": "worker2_b"},
                        ]
                    }

            thread_service._http_get_page = mock_page

            cfg = RestSourceConfig(
                source_identifier=source_id,
                url="https://api.stream.internal/events",
                dataset_id=dataset_id,
                cursor_column="id",
            )
            resp = thread_service.ingest_from_rest(
                db=thread_db,
                config=cfg,
                allow_private_hosts=True,
            )
            return resp
        finally:
            thread_db.close()

    # 3. Execute concurrently with ThreadPoolExecutor
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
        f1 = executor.submit(worker_task, 1)
        f2 = executor.submit(worker_task, 2)
        r1 = f1.result()
        r2 = f2.result()

    assert r1.status == "succeeded"
    assert r2.status == "succeeded"

    # 4. Verify in PostgreSQL that:
    # - Exactly ONE IngestionCheckpoint exists for this (source_identifier, dataset_id)
    # - The checkpoint watermark progressed to the maximum watermark ("104")
    # - Exactly 3 versions exist in total (v1, v2, v3) with strictly monotonic version numbers
    # - No versions collided or duplicated
    verify_db = SessionLocal()
    try:
        checkpoints = verify_db.scalars(
            select(IngestionCheckpoint).where(
                IngestionCheckpoint.source_identifier == source_id,
                IngestionCheckpoint.dataset_id == dataset_id,
            )
        ).all()

        assert len(checkpoints) == 1, f"Expected exactly 1 checkpoint, found {len(checkpoints)}"
        cp = checkpoints[0]
        # Watermark should be the maximum of both workers
        assert cp.watermark_value == "104"
        assert cp.records_extracted == 4  # 2 records from worker 1 + 2 records from worker 2

        # Check version numbers on dataset
        versions = verify_db.scalars(
            select(DatasetVersion)
            .where(DatasetVersion.dataset_id == dataset_id)
            .order_by(DatasetVersion.version_number.asc())
        ).all()

        version_numbers = [v.version_number for v in versions]
        assert version_numbers == [1, 2, 3], f"Unexpected version sequence: {version_numbers}"
    finally:
        verify_db.close()
