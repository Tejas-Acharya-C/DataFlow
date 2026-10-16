from fastapi import APIRouter, Depends, status
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.orm import Session

from dataflow.api.deps import get_db
from dataflow.config import get_settings

router = APIRouter(prefix="/health", tags=["Health"])


@router.get("", status_code=status.HTTP_200_OK)
@router.get("/", status_code=status.HTTP_200_OK)
@router.get("/live", status_code=status.HTTP_200_OK)
def liveness():
    """Liveness probe indicating service is running."""
    return {"status": "alive", "service": "dataflow"}


@router.get("/ready")
def readiness(db: Session = Depends(get_db)):
    """Readiness probe verifying database and storage connectivity."""
    settings = get_settings()
    try:
        db.execute(text("SELECT 1"))
        db_ok = True
    except Exception:
        db_ok = False

    storage_ok = settings.get_storage_path().exists()

    all_ready = db_ok and storage_ok
    payload = {
        "status": "ready" if all_ready else "not_ready",
        "database": "connected" if db_ok else "unreachable",
        "storage": "available" if storage_ok else "unavailable",
        "version": settings.VERSION,
        "environment": settings.ENVIRONMENT,
    }

    if not all_ready:
        return JSONResponse(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, content=payload)
    return payload
