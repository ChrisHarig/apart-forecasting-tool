from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db import get_db, models
from app.schemas.forecast import ForecastBenchmarkRead, ForecastBenchmarkRequest
from app.services.forecast_benchmark import (
    create_forecast_benchmark,
    get_forecast_benchmark,
    list_country_forecast_benchmarks,
    preview_forecast_benchmark,
)

router = APIRouter(tags=["forecast-benchmarks"])


@router.post("/forecast-benchmarks/preview", response_model=ForecastBenchmarkRead, response_model_by_alias=False)
def preview_benchmark(payload: ForecastBenchmarkRequest, db: Session = Depends(get_db)) -> ForecastBenchmarkRead:
    try:
        return preview_forecast_benchmark(db, payload)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/forecast-benchmarks", response_model=ForecastBenchmarkRead, response_model_by_alias=False, status_code=201)
def create_benchmark(payload: ForecastBenchmarkRequest, db: Session = Depends(get_db)) -> models.ForecastBenchmarkRun:
    try:
        return create_forecast_benchmark(db, payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/forecast-benchmarks/{run_id}", response_model=ForecastBenchmarkRead, response_model_by_alias=False)
def get_benchmark(run_id: int, db: Session = Depends(get_db)) -> models.ForecastBenchmarkRun:
    run = get_forecast_benchmark(db, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Forecast benchmark not found")
    return run


@router.get(
    "/countries/{iso3}/forecast-benchmarks",
    response_model=list[ForecastBenchmarkRead],
    response_model_by_alias=False,
)
def get_country_benchmarks(iso3: str, db: Session = Depends(get_db)) -> list[models.ForecastBenchmarkRun]:
    try:
        return list_country_forecast_benchmarks(db, iso3)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
