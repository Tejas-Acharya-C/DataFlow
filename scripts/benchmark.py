"""Reproducible Benchmark Script for DataFlow Data Reliability Platform.

Benchmarks CSV streaming ingestion, profiling, quality evaluation,
and contract validation with quarantine partitioning.
"""

import io
import os
import platform
import sys
import tempfile
import time
from pathlib import Path
from typing import Dict, Tuple

import pandas as pd
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from dataflow.config import get_settings
from dataflow.models.contract import DataContract
from dataflow.models.dataset import Base
from dataflow.services.ingestion import IngestionService
from dataflow.services.profiling import ProfilingService
from dataflow.services.quality import QualityService
from dataflow.services.validation import ValidationService
from dataflow.storage.local import LocalStorageManager


def generate_synthetic_csv(row_count: int, invalid_ratio: float = 0.05) -> Tuple[bytes, int, int]:
    """Generate synthetic user activity CSV bytes with controlled invalid rows.

    Returns: (csv_bytes, expected_valid_count, expected_invalid_count)
    """
    invalid_rows = int(row_count * invalid_ratio)
    valid_rows = row_count - invalid_rows

    user_ids = list(range(1, row_count + 1))
    emails = [f"user_{i}@example.com" for i in user_ids]
    ages = [20 + (i % 60) for i in range(valid_rows)] + [-5] * invalid_rows  # invalid negative ages
    statuses = ["active" if i % 2 == 0 else "pending" for i in range(valid_rows)] + ["INVALID_STATUS"] * invalid_rows

    df = pd.DataFrame({
        "user_id": user_ids,
        "email": emails,
        "age": ages,
        "status": statuses,
    })

    buf = io.BytesIO()
    df.to_csv(buf, index=False, encoding="utf-8")
    return buf.getvalue(), valid_rows, invalid_rows


def run_benchmark_for_size(
    row_count: int,
    db_session,
    storage: LocalStorageManager,
) -> Dict[str, any]:
    """Run full pipeline benchmark for a specific dataset size."""
    print("\n=======================================================")
    print(f"Generating synthetic dataset with {row_count:,} rows...")
    t0 = time.perf_counter()
    csv_bytes, exp_valid, exp_invalid = generate_synthetic_csv(row_count)
    gen_time = time.perf_counter() - t0
    size_mb = len(csv_bytes) / (1024 * 1024)
    print(f"Dataset generated: {size_mb:.2f} MB in {gen_time:.2f}s")

    ingestion_service = IngestionService(storage=storage)
    profiling_service = ProfilingService(storage=storage)
    quality_service = QualityService(storage=storage)
    validation_service = ValidationService(storage=storage)

    # 1. Ingestion Phase
    print("Executing Ingestion & Checksum Streaming...")
    t_ingest_start = time.perf_counter()
    dataset, version = ingestion_service.ingest_csv(
        db=db_session,
        file_obj=io.BytesIO(csv_bytes),
        filename=f"benchmark_{row_count}.csv",
        dataset_name=f"Benchmark_{row_count}",
    )
    t_ingest = time.perf_counter() - t_ingest_start
    ingest_throughput_rows = row_count / t_ingest
    ingest_throughput_mb = size_mb / t_ingest
    print(f"  Ingestion: {t_ingest:.3f}s ({ingest_throughput_rows:,.0f} rows/s, {ingest_throughput_mb:.2f} MB/s)")

    # 2. Profiling Phase
    print("Executing Dataset Profiling...")
    t_prof_start = time.perf_counter()
    profiling_service.profile_version(db=db_session, version=version)
    t_prof = time.perf_counter() - t_prof_start
    print(f"  Profiling: {t_prof:.3f}s")

    # 3. Quality Scoring Phase
    print("Executing Data Quality Evaluation...")
    t_qual_start = time.perf_counter()
    qual_result = quality_service.evaluate_version(db=db_session, version=version)
    t_qual = time.perf_counter() - t_qual_start
    print(f"  Quality Scoring: {t_qual:.3f}s (Quality Score: {qual_result.score})")

    # 4. Contract Validation & Quarantine Phase
    print("Executing Contract Validation & Quarantine Partitioning...")
    contract = DataContract(
        name=f"Benchmark Contract {row_count}",
        rules_json={
            "required_columns": ["user_id", "email", "age", "status"],
            "numeric_ranges": {"age": {"min": 0, "max": 120}},
            "allowed_values": {"status": ["active", "pending", "suspended"]},
        },
    )
    db_session.add(contract)
    db_session.commit()

    t_val_start = time.perf_counter()
    val_run = validation_service.validate_version(db=db_session, version=version, contract=contract)
    t_val = time.perf_counter() - t_val_start
    val_throughput_rows = row_count / t_val
    print(f"  Validation & Quarantine: {t_val:.3f}s ({val_throughput_rows:,.0f} rows/s)")
    print(f"  Result: Accepted={val_run.accepted_rows:,}, Rejected={val_run.rejected_rows:,}")

    total_time = t_ingest + t_prof + t_qual + t_val

    return {
        "rows": row_count,
        "size_mb": round(size_mb, 2),
        "ingest_time_s": round(t_ingest, 3),
        "ingest_rows_per_s": round(ingest_throughput_rows, 1),
        "ingest_mb_per_s": round(ingest_throughput_mb, 2),
        "profiling_time_s": round(t_prof, 3),
        "quality_time_s": round(t_qual, 3),
        "validation_time_s": round(t_val, 3),
        "validation_rows_per_s": round(val_throughput_rows, 1),
        "total_pipeline_time_s": round(total_time, 3),
        "accepted_rows": val_run.accepted_rows,
        "rejected_rows": val_run.rejected_rows,
        "overall_quality_score": qual_result.score,
    }


def main():
    settings = get_settings()
    db_url = settings.get_effective_database_url()

    print("=================================================================")
    print("      DATAFLOW PERFORMANCE & RELIABILITY BENCHMARK SUITE       ")
    print("=================================================================")
    print(f"OS: {platform.system()} {platform.release()} ({platform.machine()})")
    print(f"Python: {sys.version.split()[0]}")
    print(f"Database: {db_url.split('@')[-1] if '@' in db_url else db_url}")

    # Use isolated test directory for benchmark artifacts
    with tempfile.TemporaryDirectory(prefix="dataflow_bench_") as temp_dir:
        storage = LocalStorageManager(root_path=Path(temp_dir))

        engine = create_engine(db_url)
        Base.metadata.create_all(bind=engine)
        SessionLocal = sessionmaker(bind=engine)
        session = SessionLocal()

        sizes = [10_000, 100_000]
        # Include 250k if running locally for deeper analysis
        if os.environ.get("BENCHMARK_FULL") == "1":
            sizes.append(250_000)

        results = []
        try:
            for size in sizes:
                res = run_benchmark_for_size(size, session, storage)
                results.append(res)
        finally:
            session.close()

        # Format Markdown Document
        md = []
        md.append("# DataFlow Pipeline Performance Benchmark")
        md.append("")
        md.append("## Environment Specifications")
        md.append(f"- **OS**: {platform.system()} {platform.release()} ({platform.machine()})")
        md.append(f"- **Python Version**: {sys.version.split()[0]}")
        md.append("- **Storage Engine**: LocalStorageManager (Streaming SHA-256 chunked I/O)")
        md.append("- **Database Engine**: PostgreSQL / SQLAlchemy")
        md.append(f"- **Benchmark Date**: {time.strftime('%Y-%m-%d %H:%M:%S UTC', time.gmtime())}")
        md.append("")
        md.append("## Benchmark Results Summary")
        md.append("")
        md.append("| Dataset Size (Rows) | File Size | Ingestion Time | Ingestion Throughput | Validation & Quarantine | Total Pipeline Time | Accepted Rows | Rejected Rows | Quality Score |")
        md.append("|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|")

        for r in results:
            md.append(
                f"| {r['rows']:,} | {r['size_mb']} MB | {r['ingest_time_s']}s | {r['ingest_rows_per_s']:,.0f} rows/s ({r['ingest_mb_per_s']} MB/s) | {r['validation_time_s']}s ({r['validation_rows_per_s']:,.0f} rows/s) | {r['total_pipeline_time_s']}s | {r['accepted_rows']:,} | {r['rejected_rows']:,} | {r['overall_quality_score']} |"
            )

        md.append("")
        md.append("## Stage Breakdown")
        md.append("")
        md.append("| Dataset Size | Ingestion | Profiling | Quality Evaluation | Validation & Quarantine |")
        md.append("|:---:|:---:|:---:|:---:|:---:|")
        for r in results:
            md.append(
                f"| {r['rows']:,} rows | {r['ingest_time_s']}s | {r['profiling_time_s']}s | {r['quality_time_s']}s | {r['validation_time_s']}s |"
            )

        md.append("")
        md.append("## Methodology & Guarantees")
        md.append("1. **Scope of Timings**: Ingestion timings measure end-to-end streaming file write, real-time SHA-256 checksumming, header validation, schema inference, and database transactional commit.")
        md.append("2. **Correctness Coupled with Speed**: Validation timings measure full contract rule checking, row-level error identification, quarantine CSV file creation, clean CSV file creation, and individual `ValidationRejection` database row persistence.")
        md.append("3. **Zero Secrets / Synthetic Data**: Generated data is completely synthetic containing simulated user identifiers, emails, ages, and statuses with a controlled 5% error rate.")
        md.append("4. **Reproducibility**: Run `python scripts/benchmark.py` to regenerate measurements.")

        report_content = "\n".join(md)
        docs_path = Path("docs/benchmarks.md")
        docs_path.parent.mkdir(parents=True, exist_ok=True)
        docs_path.write_text(report_content, encoding="utf-8")
        print(f"\nBenchmark completed successfully! Report written to {docs_path.resolve()}")


if __name__ == "__main__":
    main()
