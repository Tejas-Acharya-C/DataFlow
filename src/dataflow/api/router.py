"""API v1 master router aggregating all sub-routers."""

from fastapi import APIRouter

from dataflow.api.endpoints.audit import router as audit_router
from dataflow.api.endpoints.contracts import router as contracts_router
from dataflow.api.endpoints.datasets import router as datasets_router
from dataflow.api.endpoints.health import router as health_router
from dataflow.api.endpoints.jobs import router as jobs_router
from dataflow.api.endpoints.profiling import router as profiling_router
from dataflow.api.endpoints.quality import router as quality_router
from dataflow.api.endpoints.transformations import router as transformations_router
from dataflow.api.endpoints.versions import router as versions_router

api_v1_router = APIRouter(prefix="/api/v1")

api_v1_router.include_router(health_router)
api_v1_router.include_router(datasets_router)
api_v1_router.include_router(versions_router)
api_v1_router.include_router(contracts_router)
api_v1_router.include_router(profiling_router)
api_v1_router.include_router(quality_router)
api_v1_router.include_router(transformations_router)
api_v1_router.include_router(jobs_router)
api_v1_router.include_router(audit_router)
