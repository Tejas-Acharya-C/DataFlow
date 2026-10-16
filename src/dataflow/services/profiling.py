"""Dataset and column profiling service."""

import math
from typing import Any, Dict, Optional

import pandas as pd
from sqlalchemy import select
from sqlalchemy.orm import Session

from dataflow.models.dataset import DatasetVersion
from dataflow.models.profiling import ProfilingResult
from dataflow.services.audit import complete_job, create_job, log_audit
from dataflow.storage.local import LocalStorageManager


def sanitize_float(val: Any) -> Optional[float]:
    """Sanitize float to ensure JSON compatibility (no NaN or Inf)."""
    if val is None or pd.isna(val):
        return None
    try:
        f = float(val)
        if math.isnan(f) or math.isinf(f):
            return None
        return round(f, 4)
    except (ValueError, TypeError):
        return None


class ProfilingService:
    """Computes comprehensive dataset and column profiling statistics."""

    def __init__(self, storage: Optional[LocalStorageManager] = None):
        self.storage = storage or LocalStorageManager()

    def profile_version(self, db: Session, version: DatasetVersion) -> ProfilingResult:
        """Run profiling on a specific dataset version."""
        job = create_job(
            db,
            job_type="profiling",
            dataset_id=version.dataset_id,
            version_id=version.id,
        )

        try:
            df = self.storage.load_dataframe(version.storage_path)

            row_count = len(df)
            col_count = len(df.columns)
            total_cells = row_count * col_count
            total_missing = int(df.isna().sum().sum())
            missing_pct = round((total_missing / total_cells * 100), 2) if total_cells > 0 else 0.0

            duplicate_rows = int(df.duplicated().sum())
            duplicate_pct = round((duplicate_rows / row_count * 100), 2) if row_count > 0 else 0.0

            summary = {
                "row_count": row_count,
                "column_count": col_count,
                "total_cells": total_cells,
                "total_missing_cells": total_missing,
                "missing_cells_percentage": missing_pct,
                "duplicate_rows_count": duplicate_rows,
                "duplicate_rows_percentage": duplicate_pct,
            }

            columns_profile = {}

            for col in df.columns:
                series = df[col]
                non_null = series.dropna()
                null_count = int(series.isna().sum())
                null_pct = round((null_count / row_count * 100), 2) if row_count > 0 else 0.0
                distinct_count = int(series.nunique(dropna=True))
                uniqueness_pct = (
                    round((distinct_count / len(non_null) * 100), 2) if len(non_null) > 0 else 0.0
                )
                is_constant = distinct_count <= 1

                # Detect type
                if pd.api.types.is_bool_dtype(series):
                    dtype = "boolean"
                elif pd.api.types.is_integer_dtype(series):
                    dtype = "integer"
                elif pd.api.types.is_float_dtype(series):
                    dtype = "float"
                elif pd.api.types.is_datetime64_any_dtype(series):
                    dtype = "datetime"
                else:
                    dtype = "string"

                col_stat: Dict[str, Any] = {
                    "name": str(col),
                    "detected_type": dtype,
                    "total_count": row_count,
                    "null_count": null_count,
                    "null_percentage": null_pct,
                    "distinct_count": distinct_count,
                    "uniqueness_percentage": uniqueness_pct,
                    "is_constant": is_constant,
                    "numeric_min": None,
                    "numeric_max": None,
                    "numeric_mean": None,
                    "numeric_median": None,
                    "numeric_std": None,
                    "string_min_length": None,
                    "string_max_length": None,
                    "string_avg_length": None,
                    "top_values": [],
                    "min_date": None,
                    "max_date": None,
                }

                # Top values
                if len(non_null) > 0:
                    val_counts = series.value_counts(dropna=True).head(10)
                    col_stat["top_values"] = [
                        {"value": str(k), "count": int(v), "percentage": round(v / row_count * 100, 2)}
                        for k, v in val_counts.items()
                    ]

                # Numeric metrics
                if pd.api.types.is_numeric_dtype(series) and not pd.api.types.is_bool_dtype(series):
                    if len(non_null) > 0:
                        col_stat["numeric_min"] = sanitize_float(series.min())
                        col_stat["numeric_max"] = sanitize_float(series.max())
                        col_stat["numeric_mean"] = sanitize_float(series.mean())
                        col_stat["numeric_median"] = sanitize_float(series.median())
                        col_stat["numeric_std"] = sanitize_float(series.std())

                # String metrics
                elif dtype == "string" and len(non_null) > 0:
                    str_lengths = non_null.astype(str).str.len()
                    col_stat["string_min_length"] = int(str_lengths.min())
                    col_stat["string_max_length"] = int(str_lengths.max())
                    col_stat["string_avg_length"] = sanitize_float(str_lengths.mean())

                    # Date detection attempt
                    try:
                        parsed_dates = pd.to_datetime(non_null.head(50), format="mixed", errors="coerce").dropna()
                        if len(parsed_dates) > 0 and len(parsed_dates) == len(non_null.head(50)):
                            all_dates = pd.to_datetime(non_null, format="mixed", errors="coerce").dropna()
                            if len(all_dates) > 0:
                                col_stat["min_date"] = str(all_dates.min())
                                col_stat["max_date"] = str(all_dates.max())
                                col_stat["detected_type"] = "datetime"
                    except Exception:
                        pass

                columns_profile[str(col)] = col_stat

            # Upsert or save profiling result
            existing = db.scalar(
                select(ProfilingResult).where(ProfilingResult.version_id == version.id)
            )
            if existing:
                existing.summary_json = summary
                existing.columns_json = columns_profile
                profiling_record = existing
            else:
                profiling_record = ProfilingResult(
                    dataset_id=version.dataset_id,
                    version_id=version.id,
                    summary_json=summary,
                    columns_json=columns_profile,
                )
                db.add(profiling_record)

            db.commit()
            db.refresh(profiling_record)

            log_audit(
                db,
                event_type="profiling.executed",
                entity_type="version",
                entity_id=version.id,
                dataset_id=version.dataset_id,
                version_id=version.id,
                details={"row_count": row_count, "column_count": col_count},
            )

            complete_job(db, job, status="succeeded")
            return profiling_record

        except Exception as exc:
            db.rollback()
            complete_job(db, job, status="failed", error_message=str(exc))
            log_audit(
                db,
                event_type="profiling.failed",
                entity_type="version",
                entity_id=version.id,
                outcome="failure",
                dataset_id=version.dataset_id,
                version_id=version.id,
                details={"error": str(exc)},
            )
            raise
