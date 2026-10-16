"""Unit tests for profiling statistics calculation."""

import io

from dataflow.services.ingestion import IngestionService
from dataflow.services.profiling import ProfilingService


def test_profiling_metrics(test_db_session, storage):
    csv_data = (
        b"id,category,score,constant_col\n"
        b"1,Alpha,80.5,CONST\n"
        b"2,Beta,92.0,CONST\n"
        b"3,Alpha,,CONST\n"
        b"4,Beta,75.0,CONST\n"
    )
    ingestion = IngestionService(storage=storage)
    dataset, version = ingestion.ingest_csv(
        db=test_db_session,
        file_obj=io.BytesIO(csv_data),
        filename="metrics.csv",
    )

    profiler = ProfilingService(storage=storage)
    result = profiler.profile_version(db=test_db_session, version=version)

    assert result.summary_json["row_count"] == 4
    assert result.summary_json["column_count"] == 4
    assert result.summary_json["total_missing_cells"] == 1

    cols = result.columns_json
    assert cols["score"]["null_count"] == 1
    assert cols["score"]["numeric_min"] == 75.0
    assert cols["score"]["numeric_max"] == 92.0
    assert cols["constant_col"]["is_constant"] is True
    assert len(cols["category"]["top_values"]) == 2
