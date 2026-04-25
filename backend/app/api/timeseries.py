from datetime import datetime

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.utils import ensure_country, ensure_source
from app.db import get_db, models
from app.schemas.observation import ObservationRead, TimeSeriesAvailabilityResponse, TimeseriesUploadResult
from app.services.normalization import NormalizationError, normalize_observation_record, parse_csv_observations
from app.services.timeseries_availability import get_timeseries_availability, validate_country_iso3

router = APIRouter(tags=["timeseries"])


@router.get("/timeseries", response_model=list[ObservationRead], response_model_by_alias=False)
def get_timeseries(
    country_iso3: str | None = Query(default=None, alias="countryIso3"),
    source_id: str | None = Query(default=None, alias="sourceId"),
    metric: str | None = None,
    start_date: datetime | None = Query(default=None, alias="startDate"),
    end_date: datetime | None = Query(default=None, alias="endDate"),
    db: Session = Depends(get_db),
) -> list[models.Observation]:
    query = select(models.Observation)
    if country_iso3:
        try:
            country_iso3 = validate_country_iso3(country_iso3)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        query = query.where(models.Observation.country_iso3 == country_iso3)
    if source_id:
        query = query.where(models.Observation.source_id == source_id)
    if metric:
        query = query.where(models.Observation.metric == metric)
    if start_date:
        query = query.where(models.Observation.observed_at >= start_date)
    if end_date:
        query = query.where(models.Observation.observed_at <= end_date)
    return db.execute(query.order_by(models.Observation.observed_at, models.Observation.id)).scalars().all()


@router.get("/timeseries/available", response_model=TimeSeriesAvailabilityResponse, response_model_by_alias=False)
def get_timeseries_availability_alias(
    country_iso3: str = Query(alias="countryIso3"),
    db: Session = Depends(get_db),
) -> TimeSeriesAvailabilityResponse:
    try:
        return get_timeseries_availability(db, country_iso3)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/timeseries/upload", response_model=TimeseriesUploadResult, response_model_by_alias=False)
async def upload_timeseries(
    file: UploadFile = File(...),
    source_id: str | None = Form(default=None, alias="sourceId"),
    country_iso3: str | None = Form(default=None, alias="countryIso3"),
    dry_run: bool = Form(default=False, alias="dryRun"),
    db: Session = Depends(get_db),
) -> TimeseriesUploadResult:
    if not file.filename.lower().endswith(".csv"):
        raise HTTPException(status_code=400, detail="Only CSV upload is supported in this scaffold")
    content = (await file.read()).decode("utf-8-sig")
    raw_rows = parse_csv_observations(content)
    inserted: list[models.Observation] = []
    errors: list[dict] = []

    for index, row in enumerate(raw_rows, start=2):
        try:
            normalized = normalize_observation_record(
                row,
                default_source_id=source_id,
                default_country_iso3=country_iso3,
            )
        except NormalizationError as exc:
            errors.append({"row": index, "error": str(exc)})
            continue

        if dry_run:
            continue

        ensure_country(db, normalized["country_iso3"])
        ensure_source(db, normalized["source_id"], category=normalized["signal_category"])
        observation = models.Observation(**normalized)
        db.add(observation)
        inserted.append(observation)

    if not dry_run:
        db.commit()
        for observation in inserted:
            db.refresh(observation)

    return TimeseriesUploadResult(
        inserted_count=len(inserted),
        rejected_count=len(errors),
        dry_run=dry_run,
        observations=inserted,
        errors=errors,
        warnings=[
            {
                "code": "test_or_user_data_only",
                "message": "Uploaded rows are treated as user-provided aggregate data and are not production source claims.",
            }
        ],
    )


@router.get("/metrics")
def list_metrics(
    country_iso3: str | None = Query(default=None, alias="countryIso3"),
    source_id: str | None = Query(default=None, alias="sourceId"),
    db: Session = Depends(get_db),
) -> list[dict]:
    query = select(models.Observation.metric, models.Observation.signal_category).group_by(
        models.Observation.metric,
        models.Observation.signal_category,
    )
    if country_iso3:
        query = query.where(models.Observation.country_iso3 == country_iso3.upper())
    if source_id:
        query = query.where(models.Observation.source_id == source_id)
    rows = db.execute(query).all()
    return [{"metric": metric, "signalCategory": signal_category} for metric, signal_category in rows]
