"""Safe data transformation engine and immutable version creation."""

import uuid
from typing import Any, Dict, List, Optional

import pandas as pd
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from dataflow.models.dataset import Dataset, DatasetVersion
from dataflow.services.audit import complete_job, create_job, log_audit
from dataflow.services.ingestion import IngestionService
from dataflow.storage.local import LocalStorageManager


class TransformationError(Exception):
    """Raised when transformation parameters or execution fails."""
    pass


class TransformationEngine:
    """Executes safe dataframe transformations without eval or raw SQL."""

    @staticmethod
    def apply_operations(df: pd.DataFrame, operations: List[Dict[str, Any]]) -> pd.DataFrame:
        """Apply a sequence of validated transformation operations to a dataframe copy."""
        result_df = df.copy()

        for step_idx, op_data in enumerate(operations):
            op_name = op_data.get("op")
            if not op_name:
                raise TransformationError(f"Step {step_idx}: Missing 'op' identifier.")

            if op_name == "rename_columns":
                mapping = op_data.get("mapping", {})
                if not isinstance(mapping, dict):
                    raise TransformationError("rename_columns requires a dictionary mapping.")
                result_df = result_df.rename(columns=mapping)

            elif op_name == "select_columns":
                cols = op_data.get("columns", [])
                missing = [c for c in cols if c not in result_df.columns]
                if missing:
                    raise TransformationError(f"select_columns: Columns not found: {missing}")
                result_df = result_df[cols]

            elif op_name == "drop_columns":
                cols = op_data.get("columns", [])
                existing = [c for c in cols if c in result_df.columns]
                result_df = result_df.drop(columns=existing)

            elif op_name == "remove_duplicates":
                subset = op_data.get("subset")
                keep = op_data.get("keep", "first")
                if subset:
                    missing = [c for c in subset if c not in result_df.columns]
                    if missing:
                        raise TransformationError(f"remove_duplicates: Subset columns not found: {missing}")
                result_df = result_df.drop_duplicates(subset=subset, keep=keep)

            elif op_name == "fill_missing":
                cols = op_data.get("columns", [])
                strategy = op_data.get("strategy", "constant")
                val = op_data.get("value")
                for c in cols:
                    if c in result_df.columns:
                        if strategy == "constant":
                            result_df[c] = result_df[c].fillna(val)
                        elif strategy == "mean" and pd.api.types.is_numeric_dtype(result_df[c]):
                            result_df[c] = result_df[c].fillna(result_df[c].mean())
                        elif strategy == "median" and pd.api.types.is_numeric_dtype(result_df[c]):
                            result_df[c] = result_df[c].fillna(result_df[c].median())
                        elif strategy == "mode":
                            mode_val = result_df[c].mode()
                            if len(mode_val) > 0:
                                result_df[c] = result_df[c].fillna(mode_val[0])
                        elif strategy == "forward_fill":
                            result_df[c] = result_df[c].ffill()
                        elif strategy == "backward_fill":
                            result_df[c] = result_df[c].bfill()

            elif op_name == "cast_columns":
                conversions = op_data.get("conversions", {})
                for c, target_type in conversions.items():
                    if c in result_df.columns:
                        try:
                            if target_type == "int":
                                result_df[c] = pd.to_numeric(result_df[c], errors="coerce").astype("Int64")
                            elif target_type == "float":
                                result_df[c] = pd.to_numeric(result_df[c], errors="coerce").astype(float)
                            elif target_type == "str":
                                result_df[c] = result_df[c].astype(str)
                            elif target_type == "bool":
                                result_df[c] = result_df[c].astype(bool)
                            elif target_type == "datetime":
                                result_df[c] = pd.to_datetime(result_df[c], errors="coerce")
                        except Exception as e:
                            raise TransformationError(f"cast_columns failed for {c} -> {target_type}: {e}")

            elif op_name == "filter_rows":
                col = op_data.get("column")
                operator = op_data.get("operator")
                val = op_data.get("value")

                if col not in result_df.columns:
                    raise TransformationError(f"filter_rows: Column '{col}' not found.")

                series = result_df[col]
                if operator == "eq":
                    mask = series == val
                elif operator == "neq":
                    mask = series != val
                elif operator == "gt":
                    mask = pd.to_numeric(series, errors="coerce") > float(val)
                elif operator == "gte":
                    mask = pd.to_numeric(series, errors="coerce") >= float(val)
                elif operator == "lt":
                    mask = pd.to_numeric(series, errors="coerce") < float(val)
                elif operator == "lte":
                    mask = pd.to_numeric(series, errors="coerce") <= float(val)
                elif operator == "in":
                    mask = series.isin(val if isinstance(val, list) else [val])
                elif operator == "not_in":
                    mask = ~series.isin(val if isinstance(val, list) else [val])
                elif operator == "is_null":
                    mask = series.isna()
                elif operator == "is_not_null":
                    mask = series.notna()
                elif operator == "contains":
                    mask = series.astype(str).str.contains(str(val), na=False)
                else:
                    raise TransformationError(f"filter_rows: Unsupported operator '{operator}'")

                result_df = result_df[mask]

            elif op_name == "sort_rows":
                by = op_data.get("by", [])
                ascending = op_data.get("ascending", [True] * len(by))
                missing = [c for c in by if c not in result_df.columns]
                if missing:
                    raise TransformationError(f"sort_rows: Columns not found: {missing}")
                if len(ascending) < len(by):
                    ascending = ascending + [True] * (len(by) - len(ascending))
                result_df = result_df.sort_values(by=by, ascending=ascending)

            elif op_name == "trim_strings":
                cols = op_data.get("columns") or list(result_df.select_dtypes(include=["object", "string"]).columns)
                lowercase = op_data.get("lowercase", False)
                uppercase = op_data.get("uppercase", False)
                for c in cols:
                    if c in result_df.columns:
                        s = result_df[c].astype(str).str.strip()
                        if lowercase:
                            s = s.str.lower()
                        elif uppercase:
                            s = s.str.upper()
                        result_df[c] = s

            elif op_name == "convert_dates":
                col = op_data.get("column")
                in_fmt = op_data.get("input_format")
                out_fmt = op_data.get("output_format", "%Y-%m-%d")
                if col in result_df.columns:
                    try:
                        if in_fmt:
                            dt_s = pd.to_datetime(result_df[col], format=in_fmt, errors="coerce")
                        else:
                            dt_s = pd.to_datetime(result_df[col], errors="coerce")
                        result_df[col] = dt_s.dt.strftime(out_fmt)
                    except Exception as e:
                        raise TransformationError(f"convert_dates failed on '{col}': {e}")
            else:
                raise TransformationError(f"Unknown transformation operation '{op_name}'")

        return result_df


class TransformationService:
    """Manages previews and immutable version commits of data transformations."""

    def __init__(self, storage: Optional[LocalStorageManager] = None):
        self.storage = storage or LocalStorageManager()
        self.ingestion = IngestionService(storage=self.storage)

    def preview_transformation(
        self,
        version: DatasetVersion,
        operations: List[Dict[str, Any]],
        max_rows: int = 20,
    ) -> Dict[str, Any]:
        """Compute preview of transformation without saving new version."""
        original_df = self.storage.load_dataframe(version.storage_path)
        transformed_df = TransformationEngine.apply_operations(original_df, operations)

        preview_slice = transformed_df.head(max_rows)
        # Clean nulls for json
        preview_slice = preview_slice.where(pd.notnull(preview_slice), None)

        return {
            "dataset_id": version.dataset_id,
            "version_id": version.id,
            "original_row_count": len(original_df),
            "original_column_count": len(original_df.columns),
            "new_row_count": len(transformed_df),
            "new_column_count": len(transformed_df.columns),
            "columns": list(transformed_df.columns),
            "preview_rows": preview_slice.to_dict(orient="records"),
            "operations_applied": len(operations),
        }

    def apply_transformation(
        self,
        db: Session,
        version: DatasetVersion,
        operations: List[Dict[str, Any]],
        reason: Optional[str] = None,
    ) -> DatasetVersion:
        """Execute transformation and save as an immutable new DatasetVersion."""
        job = create_job(
            db,
            job_type="transformation",
            dataset_id=version.dataset_id,
            version_id=version.id,
            metadata={"operations_count": len(operations), "reason": reason},
        )

        try:
            original_df = self.storage.load_dataframe(version.storage_path)
            transformed_df = TransformationEngine.apply_operations(original_df, operations)

            dataset = db.get(Dataset, version.dataset_id)
            if not dataset:
                raise TransformationError(f"Parent dataset {version.dataset_id} not found.")

            latest_version_num = (
                db.scalar(
                    select(func.max(DatasetVersion.version_number)).where(
                        DatasetVersion.dataset_id == dataset.id
                    )
                )
                or 0
            )
            next_version_num = latest_version_num + 1
            new_version_id = str(uuid.uuid4())

            # Save transformed dataframe to storage
            rel_path, file_size, checksum = self.storage.save_dataframe(
                dataset_id=dataset.id,
                version_id=new_version_id,
                df=transformed_df,
            )

            schema_json = self.ingestion._extract_schema(transformed_df)

            new_version = DatasetVersion(
                id=new_version_id,
                dataset_id=dataset.id,
                version_number=next_version_num,
                storage_path=rel_path,
                original_filename=f"v{next_version_num}_{version.original_filename}",
                file_size_bytes=file_size,
                checksum=checksum,
                row_count=len(transformed_df),
                column_count=len(transformed_df.columns),
                schema_json=schema_json,
                parent_version_id=version.id,
                creation_reason=reason or f"Transformation ({len(operations)} operations)",
                transformation_details={"operations": operations},
            )
            db.add(new_version)
            db.commit()
            db.refresh(new_version)

            log_audit(
                db,
                event_type="dataset.transformed",
                entity_type="version",
                entity_id=new_version.id,
                dataset_id=dataset.id,
                version_id=new_version.id,
                details={
                    "parent_version_id": version.id,
                    "version_number": next_version_num,
                    "row_count": len(transformed_df),
                    "operations_applied": len(operations),
                    "checksum": checksum,
                },
            )

            complete_job(db, job, status="succeeded")
            return new_version

        except Exception as exc:
            db.rollback()
            complete_job(db, job, status="failed", error_message=str(exc))
            log_audit(
                db,
                event_type="transformation.failed",
                entity_type="version",
                entity_id=version.id,
                outcome="failure",
                dataset_id=version.dataset_id,
                version_id=version.id,
                details={"error": str(exc)},
            )
            raise
