"""Endpoints for external data sources, REST API ingestion, and incremental watermarks."""

from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from dataflow.api.deps import get_db, get_rest_ingestion_service
from dataflow.models.dataset import IngestionCheckpoint
from dataflow.schemas.source import CheckpointResponse, RestIngestionResponse, RestSourceConfig
from dataflow.services.rest_ingestion import RestIngestionService
from dataflow.services.retry import PermanentError, TransientError

router = APIRouter(prefix="/sources", tags=["Sources"])


@router.post(
    "/rest/ingest",
    response_model=RestIngestionResponse,
    status_code=status.HTTP_200_OK,
    summary="Ingest data from an external REST API",
    description="Fetches data from an external REST API with pagination, retry handling, SSRF protection, and incremental watermarks.",
)
def ingest_rest_source(
    config: RestSourceConfig,
    allow_private_hosts: bool = Query(
        False,
        description="Whether to allow private/loopback hostnames (for testing/local development)",
    ),
    db: Session = Depends(get_db),
    service: RestIngestionService = Depends(get_rest_ingestion_service),
) -> RestIngestionResponse:
    """Execute REST extraction and canonical ingestion."""
    try:
        return service.ingest_from_rest(
            db=db,
            config=config,
            allow_private_hosts=allow_private_hosts,
        )
    except PermanentError as err:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(err))
    except TransientError as err:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Upstream service temporarily unavailable after retries: {err}",
        )
    except Exception as err:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(err))


@router.get(
    "/checkpoints",
    response_model=List[CheckpointResponse],
    summary="List incremental ingestion checkpoints",
    description="Retrieve recorded watermarks and cursors for all incremental source runs.",
)
def list_checkpoints(
    dataset_id: Optional[str] = Query(None, description="Filter by dataset ID"),
    source_identifier: Optional[str] = Query(None, description="Filter by source identifier"),
    db: Session = Depends(get_db),
) -> List[CheckpointResponse]:
    query = select(IngestionCheckpoint)
    if dataset_id:
        query = query.where(IngestionCheckpoint.dataset_id == dataset_id)
    if source_identifier:
        query = query.where(IngestionCheckpoint.source_identifier == source_identifier)

    checkpoints = db.execute(query.order_by(IngestionCheckpoint.last_run_at.desc())).scalars().all()
    return [CheckpointResponse.model_validate(cp) for cp in checkpoints]


@router.get(
    "/checkpoints/{dataset_id}",
    response_model=CheckpointResponse,
    summary="Get checkpoint for a dataset",
    description="Retrieve the latest watermark and cursor status for a given dataset.",
)
def get_dataset_checkpoint(
    dataset_id: str,
    db: Session = Depends(get_db),
) -> CheckpointResponse:
    checkpoint = db.execute(
        select(IngestionCheckpoint).where(IngestionCheckpoint.dataset_id == dataset_id)
    ).scalar_one_or_none()

    if not checkpoint:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No ingestion checkpoint found for dataset '{dataset_id}'.",
        )

    return CheckpointResponse.model_validate(checkpoint)
