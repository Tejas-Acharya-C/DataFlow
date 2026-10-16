"""API v1 master router aggregating all sub-routers."""

from fastapi import APIRouter, Depends

from dataflow.api.deps import verify_api_key
from dataflow.api.endpoints.audit import router as audit_router
from dataflow.api.endpoints.contracts import router as contracts_router
from dataflow.api.endpoints.datasets import router as datasets_router
from dataflow.api.endpoints.health import router as health_router
from dataflow.api.endpoints.jobs import router as jobs_router
from dataflow.api.endpoints.profiling import router as profiling_router
from dataflow.api.endpoints.quality import router as quality_router
from dataflow.api.endpoints.sources import router as sources_router
from dataflow.api.endpoints.transformations import router as transformations_router
from dataflow.api.endpoints.versions import router as versions_router

api_v1_router = APIRouter(prefix="/api/v1")

# Health endpoints are unconditionally accessible (e.g. k8s probes)
api_v1_router.include_router(health_router)

# Data, contract, and workflow routes are protected when AUTH_ENABLED=True
auth_deps = [Depends(verify_api_key)]
api_v1_router.include_router(datasets_router, dependencies=auth_deps)
api_v1_router.include_router(versions_router, dependencies=auth_deps)
api_v1_router.include_router(contracts_router, dependencies=auth_deps)
api_v1_router.include_router(profiling_router, dependencies=auth_deps)
api_v1_router.include_router(quality_router, dependencies=auth_deps)
api_v1_router.include_router(transformations_router, dependencies=auth_deps)
api_v1_router.include_router(jobs_router, dependencies=auth_deps)
api_v1_router.include_router(audit_router, dependencies=auth_deps)
api_v1_router.include_router(sources_router, dependencies=auth_deps)
