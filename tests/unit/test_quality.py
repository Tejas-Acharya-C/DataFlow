"""Unit tests for deterministic data quality evaluation."""

import io

from dataflow.services.ingestion import IngestionService
from dataflow.services.quality import QualityService


def test_quality_score_clean_dataset(test_db_session, storage):
    csv_data = (
        b"id,name,value\n"
        b"1,Clean1,100\n"
        b"2,Clean2,200\n"
        b"3,Clean3,300\n"
    )
    ingestion = IngestionService(storage=storage)
    dataset, version = ingestion.ingest_csv(
        db=test_db_session,
        file_obj=io.BytesIO(csv_data),
        filename="clean.csv",
    )

    quality_service = QualityService(storage=storage)
    res = quality_service.evaluate_version(db=test_db_session, version=version)

    assert res.score == 100.0
    assert res.status == "excellent"


def test_quality_score_dirty_dataset(test_db_session, storage):
    csv_data = (
        b"id,name,value\n"
        b"1, Alice ,100\n"  # whitespace
        b"1, Alice ,100\n"  # duplicate row
        b"2,,300\n"         # missing name
    )
    ingestion = IngestionService(storage=storage)
    dataset, version = ingestion.ingest_csv(
        db=test_db_session,
        file_obj=io.BytesIO(csv_data),
        filename="dirty.csv",
    )

    quality_service = QualityService(storage=storage)
    res = quality_service.evaluate_version(db=test_db_session, version=version)

    assert res.score < 100.0
    assert len(res.recommendations_json) > 0
