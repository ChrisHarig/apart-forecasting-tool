from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.utils import data_source_from_create
from app.db import get_db, models
from app.schemas.source import DataSourceCreate, DataSourcePatch, DataSourceRead, SourceCoverageRead
from app.services.source_registry import get_source_registry

router = APIRouter(prefix="/sources", tags=["sources"])


@router.get("")
def list_sources(db: Session = Depends(get_db)) -> list[dict]:
    db_sources = {source.id: source for source in db.execute(select(models.DataSource)).scalars().all()}
    output: list[dict] = []
    for source in sorted(db_sources.values(), key=lambda item: item.id):
        output.append(DataSourceRead.model_validate(source).model_dump(by_alias=False))
    for metadata in get_source_registry().list_source_metadata():
        if metadata["id"] not in db_sources:
            output.append(metadata)
    return output


@router.get("/{source_id}", response_model=DataSourceRead, response_model_by_alias=False)
def get_source(source_id: str, db: Session = Depends(get_db)) -> models.DataSource | dict:
    source = db.get(models.DataSource, source_id)
    if source is not None:
        return source
    connector = get_source_registry().get(source_id)
    if connector is None:
        raise HTTPException(status_code=404, detail="Source not found")
    for metadata in get_source_registry().list_source_metadata():
        if metadata["id"] == source_id:
            return metadata
    raise HTTPException(status_code=404, detail="Source not found")


@router.post("", response_model=DataSourceRead, response_model_by_alias=False, status_code=201)
def create_source(payload: DataSourceCreate, db: Session = Depends(get_db)) -> models.DataSource:
    source = data_source_from_create(payload)
    if db.get(models.DataSource, source.id) is not None:
        raise HTTPException(status_code=409, detail="Source id already exists")
    db.add(source)
    db.commit()
    db.refresh(source)
    return source


@router.patch("/{source_id}", response_model=DataSourceRead, response_model_by_alias=False)
def patch_source(source_id: str, payload: DataSourcePatch, db: Session = Depends(get_db)) -> models.DataSource:
    source = db.get(models.DataSource, source_id)
    if source is None:
        raise HTTPException(status_code=404, detail="Source not found in editable registry")
    updates = payload.model_dump(exclude_unset=True)
    for key, value in updates.items():
        setattr(source, key, value)
    source.updated_at = datetime.now(UTC)
    db.commit()
    db.refresh(source)
    return source


@router.get("/{source_id}/coverage", response_model=list[SourceCoverageRead], response_model_by_alias=False)
def get_source_coverage(source_id: str, db: Session = Depends(get_db)) -> list[models.SourceCoverage]:
    return db.execute(
        select(models.SourceCoverage)
        .where(models.SourceCoverage.source_id == source_id)
        .order_by(models.SourceCoverage.country_iso3)
    ).scalars().all()


@router.post("/{source_id}/validate")
def validate_source(source_id: str, country_iso3: str | None = None, db: Session = Depends(get_db)) -> dict:
    source = db.get(models.DataSource, source_id)
    connector = get_source_registry().get(source_id)
    if source is None and connector is None:
        raise HTTPException(status_code=404, detail="Source not found")
    availability = connector.check_availability(country_iso3).as_dict() if connector and country_iso3 else None
    adapter_status = source.adapter_status if source else connector.describe_source().adapter_status
    return {
        "sourceId": source_id,
        "valid": True,
        "adapterStatus": adapter_status,
        "availability": availability,
        "warnings": [
            "Validation checks metadata shape only; it does not certify data quality or prediction readiness.",
        ],
    }
