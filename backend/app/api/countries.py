from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db, models
from app.schemas.country import CountryRead
from app.schemas.observation import TimeSeriesAvailabilityResponse
from app.schemas.quality import DataQualityReportRead, FeatureAvailabilityRead
from app.schemas.source import DataSourceRead
from app.services.feature_availability import FeatureAvailabilityService
from app.services.model_eligibility import ModelEligibilityService
from app.services.source_registry import get_source_registry
from app.services.timeseries_availability import get_timeseries_availability, validate_country_iso3

router = APIRouter(prefix="/countries", tags=["countries"])


@router.get("", response_model=list[CountryRead], response_model_by_alias=False)
def list_countries(db: Session = Depends(get_db)) -> list[models.Country]:
    return db.execute(select(models.Country).order_by(models.Country.name)).scalars().all()


@router.get("/{iso3}", response_model=CountryRead, response_model_by_alias=False)
def get_country(iso3: str, db: Session = Depends(get_db)) -> models.Country | CountryRead:
    try:
        normalized_iso3 = validate_country_iso3(iso3)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    country = db.get(models.Country, normalized_iso3)
    if country is None:
        return CountryRead(
            iso3=normalized_iso3,
            name=normalized_iso3,
            metadata_json={
                "record_status": "not_loaded",
                "message": "No backend country metadata has been loaded for this valid ISO3 code.",
            },
        )
    return country


@router.get("/{iso3}/coverage")
def get_country_coverage(iso3: str, db: Session = Depends(get_db)) -> dict:
    try:
        normalized_iso3 = validate_country_iso3(iso3)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return FeatureAvailabilityService(db).country_profile(normalized_iso3)


@router.get("/{iso3}/sources")
def get_country_sources(iso3: str, db: Session = Depends(get_db)) -> list[dict]:
    try:
        iso3 = validate_country_iso3(iso3)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    rows = db.execute(
        select(models.DataSource, models.SourceCoverage)
        .join(models.SourceCoverage, models.SourceCoverage.source_id == models.DataSource.id, isouter=True)
        .where((models.SourceCoverage.country_iso3 == iso3) | (models.SourceCoverage.country_iso3.is_(None)))
    ).all()
    seen: set[str] = set()
    sources: list[dict] = []
    for source, coverage in rows:
        if source.id in seen:
            continue
        seen.add(source.id)
        sources.append(
            {
                "source": DataSourceRead.model_validate(source).model_dump(by_alias=False),
                "coverageStatus": coverage.coverage_status if coverage else "unknown",
                "coverageNotes": coverage.notes if coverage else "No country-specific coverage record.",
            }
        )

    registry = get_source_registry()
    for metadata in registry.list_source_metadata():
        source_id = metadata["id"]
        if source_id in seen:
            continue
        availability = registry.check_availability(source_id, iso3)
        sources.append(
            {
                "source": metadata,
                "coverageStatus": availability.get("status", "unknown")
                if isinstance(availability, dict)
                else availability.status,
                "coverageNotes": availability.get("coverage_notes")
                if isinstance(availability, dict)
                else availability.coverage_notes,
            }
        )
    return sources


@router.get("/{iso3}/timeseries/available", response_model=TimeSeriesAvailabilityResponse, response_model_by_alias=False)
def get_country_timeseries_availability(iso3: str, db: Session = Depends(get_db)) -> TimeSeriesAvailabilityResponse:
    try:
        return get_timeseries_availability(db, iso3)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get("/{iso3}/data-quality", response_model=list[DataQualityReportRead], response_model_by_alias=False)
def get_country_data_quality(iso3: str, db: Session = Depends(get_db)) -> list[models.DataQualityReport]:
    try:
        iso3 = validate_country_iso3(iso3)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return db.execute(
        select(models.DataQualityReport)
        .where(models.DataQualityReport.country_iso3 == iso3)
        .order_by(models.DataQualityReport.generated_at.desc())
    ).scalars().all()


@router.get("/{iso3}/features", response_model=list[FeatureAvailabilityRead], response_model_by_alias=False)
def get_country_features(iso3: str, db: Session = Depends(get_db)) -> list[dict]:
    try:
        normalized_iso3 = validate_country_iso3(iso3)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return FeatureAvailabilityService(db).compute_features(normalized_iso3)


@router.get("/{iso3}/model-readiness")
def get_country_model_readiness(iso3: str, db: Session = Depends(get_db)) -> dict:
    try:
        normalized_iso3 = validate_country_iso3(iso3)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return ModelEligibilityService(db).evaluate(normalized_iso3)
