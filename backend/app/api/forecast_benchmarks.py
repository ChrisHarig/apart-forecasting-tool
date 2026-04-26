import csv
from io import StringIO

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.orm import Session

from app.db import get_db
from app.schemas.forecast import (
    ForecastBenchmarkDatasetPreview,
    ForecastBenchmarkDatasetRead,
    ForecastBenchmarkDatasetRequest,
    ForecastBenchmarkRead,
    ForecastBenchmarkRequest,
    ForecastPredictionTemplateRow,
)
from app.services.forecast_benchmark import (
    create_benchmark_dataset,
    create_forecast_benchmark,
    get_benchmark_dataset,
    get_forecast_benchmark,
    get_prediction_template,
    list_country_forecast_benchmarks,
    preview_forecast_benchmark,
    preview_benchmark_dataset,
)

router = APIRouter(tags=["forecast-benchmarks"])


@router.post(
    "/forecast-benchmarks/datasets/preview",
    response_model=ForecastBenchmarkDatasetPreview,
    response_model_by_alias=False,
)
def preview_dataset(
    payload: ForecastBenchmarkDatasetRequest,
    db: Session = Depends(get_db),
) -> ForecastBenchmarkDatasetPreview:
    try:
        return preview_benchmark_dataset(db, payload)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post(
    "/forecast-benchmarks/datasets",
    response_model=ForecastBenchmarkDatasetRead,
    response_model_by_alias=False,
    status_code=201,
)
def create_dataset(
    payload: ForecastBenchmarkDatasetRequest,
    db: Session = Depends(get_db),
) -> ForecastBenchmarkDatasetRead:
    try:
        return create_benchmark_dataset(db, payload)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get(
    "/forecast-benchmarks/datasets/{dataset_snapshot_id}",
    response_model=ForecastBenchmarkDatasetRead,
    response_model_by_alias=False,
)
def get_dataset(dataset_snapshot_id: int, db: Session = Depends(get_db)) -> ForecastBenchmarkDatasetRead:
    dataset = get_benchmark_dataset(db, dataset_snapshot_id)
    if dataset is None:
        raise HTTPException(status_code=404, detail="Benchmark dataset snapshot not found")
    return dataset


@router.get(
    "/forecast-benchmarks/datasets/{dataset_snapshot_id}/prediction-template",
    response_model=list[ForecastPredictionTemplateRow],
    response_model_by_alias=False,
)
def get_dataset_prediction_template(
    dataset_snapshot_id: int,
    format: str = "json",
    db: Session = Depends(get_db),
) -> list[ForecastPredictionTemplateRow] | Response:
    try:
        template = get_prediction_template(db, dataset_snapshot_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    if format.lower() == "csv":
        buffer = StringIO()
        fieldnames = [
            "targetDate",
            "modelId",
            "modelName",
            "countryIso3",
            "sourceId",
            "metric",
            "predictedValue",
            "lower",
            "upper",
            "unit",
            "generatedAt",
            "provenanceUrl",
            "limitations",
        ]
        writer = csv.DictWriter(buffer, fieldnames=fieldnames)
        writer.writeheader()
        for row in template:
            writer.writerow(
                {
                    "targetDate": row.target_date.isoformat(),
                    "modelId": row.model_id or "",
                    "modelName": row.model_name or "",
                    "countryIso3": row.country_iso3,
                    "sourceId": row.source_id,
                    "metric": row.metric,
                    "predictedValue": "",
                    "lower": "",
                    "upper": "",
                    "unit": row.unit or "",
                    "generatedAt": "",
                    "provenanceUrl": "",
                    "limitations": "",
                }
            )
        return Response(content=buffer.getvalue(), media_type="text/csv")
    return template


@router.post("/forecast-benchmarks/preview", response_model=ForecastBenchmarkRead, response_model_by_alias=False)
def preview_benchmark(payload: ForecastBenchmarkRequest, db: Session = Depends(get_db)) -> ForecastBenchmarkRead:
    try:
        return preview_forecast_benchmark(db, payload)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/forecast-benchmarks", response_model=ForecastBenchmarkRead, response_model_by_alias=False, status_code=201)
def create_benchmark(payload: ForecastBenchmarkRequest, db: Session = Depends(get_db)) -> ForecastBenchmarkRead:
    try:
        return create_forecast_benchmark(db, payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/forecast-benchmarks/{run_id}", response_model=ForecastBenchmarkRead, response_model_by_alias=False)
def get_benchmark(run_id: int, db: Session = Depends(get_db)) -> ForecastBenchmarkRead:
    run = get_forecast_benchmark(db, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Forecast benchmark not found")
    return run


@router.get(
    "/countries/{iso3}/forecast-benchmarks",
    response_model=list[ForecastBenchmarkRead],
    response_model_by_alias=False,
)
def get_country_benchmarks(iso3: str, db: Session = Depends(get_db)) -> list[ForecastBenchmarkRead]:
    try:
        return list_country_forecast_benchmarks(db, iso3)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
