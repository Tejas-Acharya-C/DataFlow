"""CSV Ingestion and storage validation service."""

import io
import uuid
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from dataflow.models.dataset import Dataset, DatasetVersion
from dataflow.services.audit import complete_job, create_job, log_audit
from dataflow.storage.local import LocalStorageManager, StorageError


class IngestionError(Exception):
    """Raised during CSV ingestion validation failure."""
    pass


class IngestionService:
    """Handles end-to-end CSV upload lifecycle and metadata extraction."""

    def __init__(self, storage: Optional[LocalStorageManager] = None):
        self.storage = storage or LocalStorageManager()

    def _infer_column_type(self, series: pd.Series) -> str:
        """Infer standard data type for a pandas Series."""
        non_null = series.dropna()
        if len(non_null) == 0:
            return "string"
        if pd.api.types.is_bool_dtype(non_null):
            return "boolean"
        if pd.api.types.is_integer_dtype(non_null):
            return "integer"
        if pd.api.types.is_float_dtype(non_null):
            return "float"
        if pd.api.types.is_datetime64_any_dtype(non_null):
            return "datetime"
        # Try datetime conversion sample
        try:
            pd.to_datetime(non_null.head(20), format="mixed")
            return "datetime"
        except (ValueError, TypeError):
            pass
        return "string"

    def _extract_schema(self, df: pd.DataFrame) -> List[Dict[str, Any]]:
        """Extract schema metadata (column names and inferred types)."""
        schema = []
        for col in df.columns:
            schema.append({
                "name": str(col),
                "type": self._infer_column_type(df[col]),
                "nullable": bool(df[col].isna().any()),
            })
        return schema

    def ingest_csv(
        self,
        db: Session,
        file_obj: io.BufferedIOBase,
        filename: str,
        dataset_name: Optional[str] = None,
        dataset_id: Optional[str] = None,
        description: Optional[str] = None,
    ) -> Tuple[Dataset, DatasetVersion]:
        """
        Process uploaded CSV file, validate format, store file, and record dataset metadata.
        """
        if not filename.lower().endswith(".csv"):
            raise IngestionError(f"Unsupported file format: {filename}. Only CSV files are accepted.")

        job = create_job(db, job_type="ingestion", metadata={"filename": filename})

        try:
            # First, read initial sample to validate content and structure
            sample_buffer = io.BytesIO()
            first_chunk = file_obj.read(64 * 1024)
            if not first_chunk or len(first_chunk.strip()) == 0:
                raise IngestionError("Uploaded CSV file is empty.")

            sample_buffer.write(first_chunk)
            sample_buffer.seek(0)

            # Check raw header line for duplicate column headers
            try:
                first_line = first_chunk.decode("utf-8").splitlines()[0]
            except UnicodeDecodeError:
                first_line = first_chunk.decode("latin-1").splitlines()[0]

            import csv
            header_reader = csv.reader([first_line])
            raw_headers = next(header_reader, [])
            if not raw_headers or all(h.strip() == "" for h in raw_headers):
                raise IngestionError("CSV file has no columns or headers.")

            header_names = [h.strip() for h in raw_headers]
            if len(header_names) != len(set(header_names)):
                duplicates = [c for c in header_names if header_names.count(c) > 1]
                raise IngestionError(f"CSV contains duplicate column headers: {list(set(duplicates))}")

            # Try reading sample dataframe
            try:
                pd.read_csv(sample_buffer, nrows=20, encoding="utf-8")
            except UnicodeDecodeError:
                sample_buffer.seek(0)
                pd.read_csv(sample_buffer, nrows=20, encoding="latin-1")
            except Exception as e:
                raise IngestionError(f"Malformed CSV content: {e}")

            # Prepare combined stream for full storage
            # Seek back to 0 or chain streams
            file_obj.seek(0)

            # Resolve or create Dataset
            if dataset_id:
                dataset = db.get(Dataset, dataset_id)
                if not dataset or dataset.is_deleted:
                    raise IngestionError(f"Dataset with ID {dataset_id} not found.")
            else:
                effective_name = dataset_name or filename.rsplit(".", 1)[0]
                dataset = Dataset(
                    id=str(uuid.uuid4()),
                    name=effective_name,
                    description=description,
                )
                db.add(dataset)
                db.flush()

            # Determine next version number
            latest_version_num = (
                db.scalar(
                    select(func.max(DatasetVersion.version_number)).where(
                        DatasetVersion.dataset_id == dataset.id
                    )
                )
                or 0
            )
            next_version_num = latest_version_num + 1
            version_id = str(uuid.uuid4())

            # Save stream to storage safely
            try:
                rel_path, file_size, checksum = self.storage.save_stream(
                    dataset_id=dataset.id,
                    version_id=version_id,
                    file_stream=file_obj,
                )
            except StorageError as se:
                raise IngestionError(str(se))

            # Inspect full dataframe for exact row/column metrics
            full_df = self.storage.load_dataframe(rel_path)
            row_count = len(full_df)
            col_count = len(full_df.columns)
            schema_json = self._extract_schema(full_df)

            # Create immutable DatasetVersion record
            version = DatasetVersion(
                id=version_id,
                dataset_id=dataset.id,
                version_number=next_version_num,
                storage_path=rel_path,
                original_filename=filename,
                file_size_bytes=file_size,
                checksum=checksum,
                row_count=row_count,
                column_count=col_count,
                schema_json=schema_json,
                creation_reason="initial_upload" if next_version_num == 1 else "version_upload",
            )
            db.add(version)
            db.commit()
            db.refresh(dataset)
            db.refresh(version)

            log_audit(
                db,
                event_type="dataset.uploaded",
                entity_type="dataset",
                entity_id=dataset.id,
                dataset_id=dataset.id,
                version_id=version.id,
                details={
                    "filename": filename,
                    "version_number": next_version_num,
                    "row_count": row_count,
                    "column_count": col_count,
                    "checksum": checksum,
                },
            )

            complete_job(db, job, status="succeeded")
            return dataset, version

        except Exception as exc:
            db.rollback()
            complete_job(db, job, status="failed", error_message=str(exc))
            log_audit(
                db,
                event_type="dataset.upload_failed",
                entity_type="dataset",
                entity_id=dataset_id or "unknown",
                outcome="failure",
                details={"error": str(exc), "filename": filename},
            )
            raise
