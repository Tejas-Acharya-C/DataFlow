"""Data contracts and validation run endpoints."""

from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from dataflow.api.deps import get_db, get_storage_manager, get_validation_service
from dataflow.models.contract import DataContract, ValidationRun
from dataflow.models.dataset import DatasetVersion
from dataflow.schemas.contract import (
    ContractCreate,
    ContractResponse,
    ContractUpdate,
    ValidationRejectionListResponse,
    ValidationRejectionResponse,
    ValidationRunResponse,
)
from dataflow.services.audit import log_audit
from dataflow.services.validation import ValidationService
from dataflow.storage.local import LocalStorageManager

router = APIRouter(tags=["Contracts & Validation"])


class ValidateRequest(BaseModel):
    version_id: str


@router.post("/contracts", response_model=ContractResponse, status_code=status.HTTP_201_CREATED)
def create_contract(
    payload: ContractCreate,
    db: Session = Depends(get_db),
):
    """Create a new reusable data contract."""
    existing = db.scalar(select(DataContract).where(DataContract.name == payload.name))
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Contract with name '{payload.name}' already exists.",
        )

    contract = DataContract(
        name=payload.name,
        description=payload.description,
        version=1,
        rules_json=payload.rules.model_dump(),
    )
    db.add(contract)
    db.commit()
    db.refresh(contract)

    log_audit(
        db,
        event_type="contract.created",
        entity_type="contract",
        entity_id=contract.id,
        details={"name": contract.name},
    )

    return contract


@router.get("/contracts", response_model=List[ContractResponse])
def list_contracts(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    db: Session = Depends(get_db),
):
    """List all available data contracts."""
    contracts = db.scalars(
        select(DataContract).order_by(DataContract.created_at.desc()).offset(skip).limit(limit)
    ).all()
    return [ContractResponse.model_validate(c) for c in contracts]


@router.get("/contracts/{contract_id}", response_model=ContractResponse)
def get_contract(
    contract_id: str,
    db: Session = Depends(get_db),
):
    """Get contract details by ID."""
    contract = db.get(DataContract, contract_id)
    if not contract:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Contract not found.")
    return contract


@router.put("/contracts/{contract_id}", response_model=ContractResponse)
def update_contract(
    contract_id: str,
    payload: ContractUpdate,
    db: Session = Depends(get_db),
):
    """Update contract rules and increment contract version."""
    contract = db.get(DataContract, contract_id)
    if not contract:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Contract not found.")

    if payload.description is not None:
        contract.description = payload.description
    if payload.rules is not None:
        contract.rules_json = payload.rules.model_dump()
        contract.version += 1

    db.commit()
    db.refresh(contract)

    log_audit(
        db,
        event_type="contract.updated",
        entity_type="contract",
        entity_id=contract.id,
        details={"version": contract.version},
    )

    return contract


@router.delete("/contracts/{contract_id}", status_code=status.HTTP_200_OK)
def delete_contract(
    contract_id: str,
    db: Session = Depends(get_db),
):
    """Delete a contract."""
    contract = db.get(DataContract, contract_id)
    if not contract:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Contract not found.")

    name = contract.name
    db.delete(contract)
    db.commit()

    log_audit(
        db,
        event_type="contract.deleted",
        entity_type="contract",
        entity_id=contract_id,
        details={"name": name},
    )

    return {"message": f"Contract '{name}' deleted.", "id": contract_id}


@router.post("/contracts/{contract_id}/validate", response_model=ValidationRunResponse)
def validate_dataset_version(
    contract_id: str,
    payload: ValidateRequest,
    db: Session = Depends(get_db),
    service: ValidationService = Depends(get_validation_service),
):
    """Run data contract validation checks on a dataset version."""
    contract = db.get(DataContract, contract_id)
    if not contract:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Contract not found.")

    version = db.get(DatasetVersion, payload.version_id)
    if not version:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Dataset version not found.")

    try:
        run = service.validate_version(db=db, version=version, contract=contract)
        return run
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Validation execution failed: {exc}",
        )


@router.get("/validations", response_model=List[ValidationRunResponse])
def list_validation_runs(
    dataset_id: Optional[str] = Query(None),
    version_id: Optional[str] = Query(None),
    contract_id: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=100),
    db: Session = Depends(get_db),
):
    """List historical validation runs with optional filters."""
    stmt = select(ValidationRun).order_by(ValidationRun.executed_at.desc())
    if dataset_id:
        stmt = stmt.where(ValidationRun.dataset_id == dataset_id)
    if version_id:
        stmt = stmt.where(ValidationRun.version_id == version_id)
    if contract_id:
        stmt = stmt.where(ValidationRun.contract_id == contract_id)

    runs = db.scalars(stmt.limit(limit)).all()
    return [ValidationRunResponse.model_validate(r) for r in runs]


@router.get("/validations/{run_id}", response_model=ValidationRunResponse)
def get_validation_run(
    run_id: str,
    db: Session = Depends(get_db),
):
    """Retrieve full validation run results by ID."""
    run = db.get(ValidationRun, run_id)
    if not run:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Validation run not found.")
    return run


@router.get("/validations/{run_id}/rejections", response_model=ValidationRejectionListResponse)
def get_validation_rejections(
    run_id: str,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    db: Session = Depends(get_db),
    service: ValidationService = Depends(get_validation_service),
):
    """Retrieve paginated row-level rejected records and failure reasons for a validation run."""
    run = db.get(ValidationRun, run_id)
    if not run:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Validation run not found.")

    items, total = service.get_rejections(db, run_id=run_id, skip=skip, limit=limit)
    return ValidationRejectionListResponse(
        items=[ValidationRejectionResponse.model_validate(it) for it in items],
        total=total,
        run_id=run_id,
        accepted_rows=run.accepted_rows,
        rejected_rows=run.rejected_rows,
    )


@router.get("/validations/{run_id}/quarantine/download")
def download_quarantine_records(
    run_id: str,
    db: Session = Depends(get_db),
    storage: LocalStorageManager = Depends(get_storage_manager),
):
    """Download quarantined invalid records as CSV."""
    run = db.get(ValidationRun, run_id)
    if not run:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Validation run not found.")
    if not run.quarantine_path:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No quarantined records for this run.")

    return StreamingResponse(
        storage.file_stream(run.quarantine_path),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="quarantine_{run_id[:8]}.csv"'},
    )


@router.get("/validations/{run_id}/clean/download")
def download_clean_records(
    run_id: str,
    db: Session = Depends(get_db),
    storage: LocalStorageManager = Depends(get_storage_manager),
):
    """Download validated clean records as CSV."""
    run = db.get(ValidationRun, run_id)
    if not run:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Validation run not found.")
    if not run.clean_path:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No clean records for this run.")

    return StreamingResponse(
        storage.file_stream(run.clean_path),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="clean_{run_id[:8]}.csv"'},
    )
