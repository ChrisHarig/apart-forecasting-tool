from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, Response, UploadFile
from sqlalchemy.orm import Session

from app.db import get_db
from app.schemas.forecast import ForecastModelRead, ForecastPredictionUploadResult, UploadedPredictionSetRead
from app.services.forecast_benchmark import (
    delete_prediction_set,
    get_forecast_model,
    get_prediction_set,
    list_forecast_models,
    list_prediction_sets,
    reject_executable_prediction_filename,
    upload_forecast_predictions,
)
from app.services.normalization import NormalizationError

router = APIRouter(prefix="/forecast-models", tags=["forecast-models"])


@router.get("", response_model=list[ForecastModelRead], response_model_by_alias=False)
def get_forecast_models(
    include_experimental: bool = Query(False, alias="includeExperimental"),
    db: Session = Depends(get_db),
) -> list[ForecastModelRead]:
    return list_forecast_models(db, include_experimental=include_experimental)


@router.post("/predictions/upload", response_model=ForecastPredictionUploadResult, response_model_by_alias=False)
async def upload_prediction_csv(
    file: UploadFile = File(...),
    benchmark_dataset_snapshot_id: int | None = Form(None),
    country_iso3: str | None = Form(None),
    source_id: str | None = Form(None),
    metric: str | None = Form(None),
    unit: str | None = Form(None),
    model_id: str | None = Form(None),
    model_name: str | None = Form(None),
    frequency: str | None = Form(None),
    horizon_periods: int | None = Form(None),
    user_notes: str | None = Form(None),
    submitter_name: str | None = Form(None, alias="submitterName"),
    submitter_email: str | None = Form(None, alias="submitterEmail"),
    organization: str | None = Form(None),
    submission_track: str | None = Form(None, alias="submissionTrack"),
    method_summary: str | None = Form(None, alias="methodSummary"),
    model_url: str | None = Form(None, alias="modelUrl"),
    code_url: str | None = Form(None, alias="codeUrl"),
    provenance_url: str | None = Form(None, alias="provenanceUrl"),
    visibility: str | None = Form(None),
    disclosure_notes: str | None = Form(None, alias="disclosureNotes"),
    verified_group: bool = Form(False, alias="verifiedGroup"),
    db: Session = Depends(get_db),
) -> ForecastPredictionUploadResult:
    try:
        reject_executable_prediction_filename(file.filename)
        content = (await file.read()).decode("utf-8-sig")
        return upload_forecast_predictions(
            db,
            content,
            benchmark_dataset_snapshot_id=benchmark_dataset_snapshot_id,
            country_iso3=country_iso3,
            source_id=source_id,
            metric=metric,
            unit=unit,
            model_id=model_id,
            model_name=model_name,
            frequency=frequency,
            horizon_periods=horizon_periods,
            user_notes=user_notes,
            submitter_name=submitter_name,
            submitter_email=submitter_email,
            organization=organization,
            submission_track=submission_track,
            method_summary=method_summary,
            model_url=model_url,
            code_url=code_url,
            provenance_url=provenance_url,
            visibility=visibility,
            disclosure_notes=disclosure_notes,
            verified_group=verified_group,
        )
    except NormalizationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/predictions", response_model=list[UploadedPredictionSetRead], response_model_by_alias=False)
def get_prediction_sets(
    country_iso3: str | None = Query(None, alias="countryIso3"),
    source_id: str | None = Query(None, alias="sourceId"),
    metric: str | None = None,
    dataset_snapshot_id: int | None = Query(None, alias="datasetSnapshotId"),
    model_id: str | None = Query(None, alias="modelId"),
    db: Session = Depends(get_db),
) -> list[UploadedPredictionSetRead]:
    try:
        return list_prediction_sets(
            db,
            country_iso3=country_iso3,
            source_id=source_id,
            metric=metric,
            dataset_snapshot_id=dataset_snapshot_id,
            model_id=model_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get("/predictions/{prediction_set_id}", response_model=UploadedPredictionSetRead, response_model_by_alias=False)
def get_prediction_set_detail(prediction_set_id: int, db: Session = Depends(get_db)) -> UploadedPredictionSetRead:
    prediction_set = get_prediction_set(db, prediction_set_id)
    if prediction_set is None:
        raise HTTPException(status_code=404, detail="Uploaded prediction set not found")
    return prediction_set


@router.delete("/predictions/{prediction_set_id}", status_code=204)
def remove_prediction_set(prediction_set_id: int, db: Session = Depends(get_db)) -> Response:
    if not delete_prediction_set(db, prediction_set_id):
        raise HTTPException(status_code=404, detail="Uploaded prediction set not found")
    return Response(status_code=204)


@router.get("/{model_id}", response_model=ForecastModelRead, response_model_by_alias=False)
def get_forecast_model_detail(model_id: str, db: Session = Depends(get_db)) -> ForecastModelRead:
    model = get_forecast_model(db, model_id)
    if model is None:
        raise HTTPException(status_code=404, detail="Forecast model not found")
    return model
