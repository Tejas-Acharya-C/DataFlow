"""FastAPI entry point for the DataFlow platform."""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from dataflow.api.router import api_v1_router
from dataflow.config import get_settings
from dataflow.storage.local import LocalStorageManager

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("dataflow")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan context for initialization and cleanup."""
    settings = get_settings()
    logger.info(f"Starting {settings.PROJECT_NAME} v{settings.VERSION} [{settings.ENVIRONMENT}]")
    storage = LocalStorageManager()
    logger.info(f"Storage root initialized at: {storage.root_path}")

    # Reconcile any lingering jobs from previous crashes/restarts
    try:
        from dataflow.db.session import SessionLocal
        from dataflow.services.audit import reconcile_stale_jobs
        with SessionLocal() as db:
            reconcile_stale_jobs(db)
    except Exception as e:
        logger.debug(f"Could not run startup job reconciliation: {e}")

    yield
    logger.info("Shutting down DataFlow application.")


def create_app() -> FastAPI:
    """Instantiate and configure FastAPI application."""
    settings = get_settings()

    app = FastAPI(
        title="DataFlow API",
        description="Data reliability platform for ingesting, validating, profiling, transforming, and versioning datasets.",
        version=settings.VERSION,
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
        lifespan=lifespan,
    )

    # Configure CORS
    cors_origins = (
        settings.CORS_ORIGINS
        if isinstance(settings.CORS_ORIGINS, list)
        else [settings.CORS_ORIGINS]
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=cors_origins or ["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Global Exception Handlers
    @app.exception_handler(Exception)
    async def global_exception_handler(request: Request, exc: Exception):
        logger.error(f"Unhandled error processing {request.method} {request.url.path}: {exc}", exc_info=True)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"detail": "An internal server error occurred.", "error_type": type(exc).__name__},
        )

    # Mount API v1 router
    app.include_router(api_v1_router)

    @app.get("/", tags=["Root"])
    def root():
        return {
            "name": settings.PROJECT_NAME,
            "version": settings.VERSION,
            "docs": "/docs",
            "health": "/api/v1/health/live",
        }

    return app


app = create_app()

if __name__ == "__main__":
    import uvicorn
    settings = get_settings()
    uvicorn.run("dataflow.main:app", host=settings.HOST, port=settings.PORT, reload=True)
