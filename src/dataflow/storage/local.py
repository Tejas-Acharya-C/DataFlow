"""Local filesystem storage manager for DataFlow artifacts."""

import hashlib
import io
from pathlib import Path
from typing import Any, Dict, Generator, List, Optional, Tuple

import pandas as pd

from dataflow.config import get_settings


class StorageError(Exception):
    """Base exception for storage operations."""
    pass


class PathTraversalError(StorageError):
    """Raised when an unsafe path traversal attempt is detected."""
    pass


class LocalStorageManager:
    """Manages CSV dataset files on local filesystem safely."""

    def __init__(self, root_path: Optional[Path] = None):
        self.settings = get_settings()
        self.root_path = (root_path or self.settings.get_storage_path()).resolve()
        self.root_path.mkdir(parents=True, exist_ok=True)

    def _resolve_safe_path(self, relative_path: str) -> Path:
        """Resolve path and verify it stays inside root_path."""
        target = (self.root_path / relative_path).resolve()
        try:
            target.relative_to(self.root_path)
        except ValueError:
            raise PathTraversalError(f"Access outside storage root is prohibited: {relative_path}")
        return target

    def save_stream(
        self,
        dataset_id: str,
        version_id: str,
        file_stream: io.BufferedIOBase,
        max_bytes: Optional[int] = None,
    ) -> Tuple[str, int, str]:
        """
        Stream file content to storage, computing SHA-256 hash and size.
        Returns: (relative_storage_path, file_size_bytes, sha256_checksum)
        """
        max_limit = max_bytes or self.settings.MAX_UPLOAD_SIZE_BYTES
        rel_dir = Path("datasets") / dataset_id
        target_dir = self._resolve_safe_path(str(rel_dir))
        target_dir.mkdir(parents=True, exist_ok=True)

        target_file = target_dir / f"{version_id}.csv"
        if target_file.exists():
            raise StorageError(f"Target artifact already exists at {target_file}")

        hasher = hashlib.sha256()
        total_size = 0
        chunk_size = 64 * 1024  # 64 KB

        with open(target_file, "wb") as dest:
            while True:
                chunk = file_stream.read(chunk_size)
                if not chunk:
                    break
                total_size += len(chunk)
                if total_size > max_limit:
                    dest.close()
                    target_file.unlink(missing_ok=True)
                    raise StorageError(
                        f"File size exceeds maximum allowed upload limit of {max_limit} bytes"
                    )
                hasher.update(chunk)
                dest.write(chunk)

        checksum = hasher.hexdigest()
        rel_path = f"datasets/{dataset_id}/{version_id}.csv"
        return rel_path, total_size, checksum

    def save_dataframe(
        self,
        dataset_id: str,
        version_id: str,
        df: pd.DataFrame,
    ) -> Tuple[str, int, str]:
        """Save a pandas DataFrame directly to CSV in storage."""
        rel_dir = Path("datasets") / dataset_id
        target_dir = self._resolve_safe_path(str(rel_dir))
        target_dir.mkdir(parents=True, exist_ok=True)

        target_file = target_dir / f"{version_id}.csv"
        df.to_csv(target_file, index=False)

        # Calculate checksum & size
        hasher = hashlib.sha256()
        with open(target_file, "rb") as f:
            while chunk := f.read(64 * 1024):
                hasher.update(chunk)
        size = target_file.stat().st_size
        rel_path = f"datasets/{dataset_id}/{version_id}.csv"
        return rel_path, size, hasher.hexdigest()

    def get_absolute_path(self, relative_path: str) -> Path:
        """Get verified absolute path for an artifact."""
        safe_path = self._resolve_safe_path(relative_path)
        if not safe_path.exists():
            raise StorageError(f"Artifact not found at {relative_path}")
        return safe_path

    def read_preview(
        self,
        relative_path: str,
        max_rows: Optional[int] = None,
    ) -> Tuple[List[str], List[Dict[str, Any]], int]:
        """
        Read bounded preview rows from a stored CSV file.
        Returns: (columns, rows_as_dicts, total_rows_estimated)
        """
        safe_path = self.get_absolute_path(relative_path)
        limit = max_rows or self.settings.MAX_PREVIEW_ROWS

        # Try utf-8 first, fallback to latin-1
        try:
            df = pd.read_csv(safe_path, nrows=limit, encoding="utf-8")
        except UnicodeDecodeError:
            df = pd.read_csv(safe_path, nrows=limit, encoding="latin-1")

        # Replace NaN / Inf with None for valid JSON serialization
        df = df.where(pd.notnull(df), None)
        columns = list(df.columns)
        records = df.to_dict(orient="records")
        return columns, records, len(records)

    def load_dataframe(self, relative_path: str) -> pd.DataFrame:
        """Load full dataframe from storage."""
        safe_path = self.get_absolute_path(relative_path)
        try:
            return pd.read_csv(safe_path, encoding="utf-8")
        except UnicodeDecodeError:
            return pd.read_csv(safe_path, encoding="latin-1")

    def file_stream(self, relative_path: str) -> Generator[bytes, None, None]:
        """Stream chunks of a file for download."""
        safe_path = self.get_absolute_path(relative_path)
        with open(safe_path, "rb") as f:
            while chunk := f.read(64 * 1024):
                yield chunk

    def delete_artifact(self, relative_path: str) -> bool:
        """Safely delete a stored artifact."""
        try:
            safe_path = self._resolve_safe_path(relative_path)
            if safe_path.exists() and safe_path.is_file():
                safe_path.unlink()
                return True
            return False
        except Exception:
            return False

    def read_bytes(self, relative_path: str) -> bytes:
        """Read raw bytes of a stored artifact safely."""
        return self.get_absolute_path(relative_path).read_bytes()
