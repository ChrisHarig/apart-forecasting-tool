from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.db import get_db
from app.schemas.forecast import ForecastModelRead, ForecastPredictionUploadResult
from app.services.forecast_benchmark import (
    get_forecast_model,
    list_forecast_models,
    upload_forecast_predictions,
)
from app.services.normalization import NormalizationError

router = APIRouter(prefix="/forecast-models", tags=["forecast-models"])


@router.get("", response_model=list[ForecastModelRead], response_model_by_alias=False)
def get_forecast_models(db: Session = Depends(get_db)) -> list[ForecastModelRead]:
    return list_forecast_models(db)


@router.get("/{model_id}", response_model=ForecastModelRead, response_model_by_alias=False)
def get_forecast_model_detail(model_id: str, db: Session = Depends(get_db)) -> ForecastModelRead:
    model = get_forecast_model(db, model_id)
    if model is None:
        raise HTTPException(status_code=404, detail="Forecast model not found")
    return model


@router.post("/predictions/upload", response_model=ForecastPredictionUploadResult, response_model_by_alias=False)
async def upload_prediction_csv(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
) -> ForecastPredictionUploadResult:
    if not file.filename.lower().endswith(".csv"):
        raise HTTPException(
            status_code=400,
            detail="Only forecast prediction CSV upload is supported; executable model artifacts are not accepted.",
        )
    try:
        content = (await file.read()).decode("utf-8-sig")
        return upload_forecast_predictions(db, content)
    except NormalizationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

