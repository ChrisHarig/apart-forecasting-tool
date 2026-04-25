from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session, selectinload
from sqlalchemy import select

from app.api.utils import ensure_country
from app.db import get_db, models
from app.schemas.model import ModelReadiness, ModelRunRead, ModelRunRequest
from app.services.model_eligibility import ModelEligibilityService
from app.services.normalization import serializable

router = APIRouter(prefix="/model-runs", tags=["model-runs"])


@router.post("/preview", response_model=ModelReadiness, response_model_by_alias=False)
def preview_model_run(payload: ModelRunRequest, db: Session = Depends(get_db)) -> dict:
    return ModelEligibilityService(db).evaluate(
        payload.country_iso3,
        requested_model_id=payload.selected_model_id,
        horizon_days=payload.horizon_days,
        target_signal=payload.target_signal,
    )


@router.post("", response_model=ModelRunRead, response_model_by_alias=False, status_code=201)
def create_model_run(payload: ModelRunRequest, db: Session = Depends(get_db)) -> models.ModelRun:
    ensure_country(db, payload.country_iso3)
    service = ModelEligibilityService(db)
    eligibility = service.evaluate(
        payload.country_iso3,
        requested_model_id=payload.selected_model_id,
        horizon_days=payload.horizon_days,
        target_signal=payload.target_signal,
    )
    output_points = service.build_placeholder_output_points(eligibility)
    output_status = eligibility["output_status"]
    if eligibility["selected_model_id"] != "insufficient_data" and not output_points:
        output_status = "partial"
        eligibility["warnings"].append(
            {
                "code": "no_output_points",
                "message": "Model was eligible, but this scaffold produced no numeric output points for the selected model.",
                "severity": "info",
            }
        )
    eligibility_json = serializable(eligibility)

    model_run = models.ModelRun(
        country_iso3=payload.country_iso3.upper(),
        horizon_days=payload.horizon_days,
        target_signal=payload.target_signal,
        selected_model_id=eligibility["selected_model_id"],
        model_eligibility=eligibility_json,
        input_feature_snapshot=serializable({"features": eligibility["features"], "sourcesUsed": eligibility["sources_used"]}),
        data_quality_snapshot=serializable({"score": eligibility["data_quality_score"]}),
        output_status=output_status,
        explanation=eligibility["explanation"],
        warnings=serializable(eligibility["warnings"]),
    )
    for point in output_points:
        model_run.output_points.append(models.ModelOutputPoint(**point))
    db.add(model_run)
    db.commit()
    return db.execute(
        select(models.ModelRun)
        .where(models.ModelRun.id == model_run.id)
        .options(selectinload(models.ModelRun.output_points))
    ).scalar_one()


@router.get("/{run_id}", response_model=ModelRunRead, response_model_by_alias=False)
def get_model_run(run_id: int, db: Session = Depends(get_db)) -> models.ModelRun:
    run = db.execute(
        select(models.ModelRun)
        .where(models.ModelRun.id == run_id)
        .options(selectinload(models.ModelRun.output_points))
    ).scalar_one_or_none()
    if run is None:
        raise HTTPException(status_code=404, detail="Model run not found")
    return run
