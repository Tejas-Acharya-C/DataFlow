from __future__ import annotations

import secrets
from typing import TYPE_CHECKING, Optional

from fastapi import Depends, HTTPException, Security, status
from fastapi.security import APIKeyHeader

from dataflow.config import Settings, get_settings
from dataflow.db.session import get_db
from dataflow.services.ingestion import IngestionService
from dataflow.services.profiling import ProfilingService
from dataflow.services.quality import QualityService
from dataflow.services.transformation import TransformationService
from dataflow.services.validation import ValidationService
from dataflow.storage.local import LocalStorageManager

if TYPE_CHECKING:
    from dataflow.services.rest_ingestion import RestIngestionService


__all__ = [
    "get_db",
    "get_storage_manager",
    "get_ingestion_service",
    "get_profiling_service",
    "get_validation_service",
    "get_quality_service",
    "get_transformation_service",
    "get_rest_ingestion_service",
    "verify_api_key",
]

api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


def verify_api_key(
    api_key: Optional[str] = Security(api_key_header),
    settings: Settings = Depends(get_settings),
) -> Optional[str]:
    """Verify incoming API key header against environment configuration.

    If AUTH_ENABLED is False (development/testing default), the check passes.
    If AUTH_ENABLED is True, a valid DATAFLOW_API_KEY must be provided via the
    'X-API-Key' header and is verified using constant-time comparison.
    """
    if not settings.AUTH_ENABLED:
        return api_key

    expected_key = settings.API_KEY
    if not expected_key:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Server authentication misconfigured: DATAFLOW_API_KEY is not set.",
        )

    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing API key in 'X-API-Key' header.",
            headers={"WWW-Authenticate": "ApiKey"},
        )

    if not secrets.compare_digest(api_key.strip(), expected_key.strip()):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key.",
            headers={"WWW-Authenticate": "ApiKey"},
        )

    return api_key


def get_storage_manager() -> LocalStorageManager:
    return LocalStorageManager()


def get_ingestion_service(
    storage: LocalStorageManager = Depends(get_storage_manager),
) -> IngestionService:
    return IngestionService(storage=storage)


def get_profiling_service(
    storage: LocalStorageManager = Depends(get_storage_manager),
) -> ProfilingService:
    return ProfilingService(storage=storage)


def get_validation_service(
    storage: LocalStorageManager = Depends(get_storage_manager),
) -> ValidationService:
    return ValidationService(storage=storage)


def get_quality_service(
    storage: LocalStorageManager = Depends(get_storage_manager),
) -> QualityService:
    return QualityService(storage=storage)


def get_transformation_service(
    storage: LocalStorageManager = Depends(get_storage_manager),
) -> TransformationService:
    return TransformationService(storage=storage)


def get_rest_ingestion_service(
    ingestion: IngestionService = Depends(get_ingestion_service),
) -> "RestIngestionService":
    from dataflow.services.rest_ingestion import RestIngestionService

    return RestIngestionService(ingestion_service=ingestion)
