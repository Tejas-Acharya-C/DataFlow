"""API dependencies and service provider factories."""

from fastapi import Depends

from dataflow.db.session import get_db
from dataflow.services.ingestion import IngestionService
from dataflow.services.profiling import ProfilingService
from dataflow.services.quality import QualityService
from dataflow.services.transformation import TransformationService
from dataflow.services.validation import ValidationService
from dataflow.storage.local import LocalStorageManager

__all__ = [
    "get_db",
    "get_storage_manager",
    "get_ingestion_service",
    "get_profiling_service",
    "get_validation_service",
    "get_quality_service",
    "get_transformation_service",
]


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
