import csv
from io import StringIO

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, Response, UploadFile
from sqlalchemy.orm import Session

from app.db import get_db
from app.schemas.forecast_challenge import (
    ForecastChallengeCreateRequest,
    ForecastChallengeListItem,
    ForecastChallengeMode,
    ForecastChallengePreviewRequest,
    ForecastChallengePreviewResponse,
    ForecastChallengeSnapshotResponse,
    ForecastChallengeStatus,
    PredictionTemplateRow,
)
from app.schemas.prediction_set import (
    BuiltInPredictionRunRequest,
    BuiltInPredictionRunResponse,
    ChallengePredictionUploadResult,
    ForecastChallengeScoreRequest,
    ForecastChallengeScoreResponse,
    ForecastComparisonPointResponse,
    ForecastLeaderboardResponse,
    PredictionSetResponse,
    ReviewDecisionRequest,
    ReviewDecisionResponse,
    SubmitterResponse,
)
from app.services.forecast_challenges import (
    build_prediction_template,
    create_forecast_challenge,
    get_forecast_challenge,
    list_forecast_challenges,
    preview_forecast_challenge,
)
from app.services.forecast_prediction_sets import (
    get_prediction_set,
    list_prediction_sets,
    run_builtin_predictions_for_challenge,
    upload_prediction_csv_for_challenge,
)
from app.services.forecast_benchmark import reject_executable_prediction_filename
from app.services.forecast_scoring import (
    build_comparison_points,
    build_leaderboard,
    score_all_prediction_sets_for_challenge,
)
from app.services.normalization import NormalizationError
from app.services.submissions import (
    apply_review_decision,
    get_latest_review_decision,
    get_submitter,
    list_submitters,
)

router = APIRouter(tags=["forecast-challenges"])


@router.post(
    "/forecast-challenges/preview",
    response_model=ForecastChallengePreviewResponse,
    response_model_by_alias=False,
)
def preview_challenge(
    payload: ForecastChallengePreviewRequest,
    db: Session = Depends(get_db),
) -> ForecastChallengePreviewResponse:
    try:
        return preview_forecast_challenge(db, payload)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post(
    "/forecast-challenges",
    response_model=ForecastChallengeSnapshotResponse,
    response_model_by_alias=False,
    status_code=201,
)
def create_challenge(
    payload: ForecastChallengeCreateRequest,
    db: Session = Depends(get_db),
) -> ForecastChallengeSnapshotResponse:
    try:
        return create_forecast_challenge(db, payload)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get(
    "/forecast-challenges",
    response_model=list[ForecastChallengeListItem],
    response_model_by_alias=False,
)
def get_challenges(
    country_iso3: str | None = Query(None, alias="countryIso3"),
    source_id: str | None = Query(None, alias="sourceId"),
    metric: str | None = None,
    mode: ForecastChallengeMode | None = None,
    status: ForecastChallengeStatus | None = None,
    db: Session = Depends(get_db),
) -> list[ForecastChallengeListItem]:
    try:
        return list_forecast_challenges(
            db,
            country_iso3=country_iso3,
            source_id=source_id,
            metric=metric,
            mode=mode,
            status=status,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get(
    "/forecast-challenges/{challenge_id}",
    response_model=ForecastChallengeSnapshotResponse,
    response_model_by_alias=False,
)
def get_challenge(challenge_id: int, db: Session = Depends(get_db)) -> ForecastChallengeSnapshotResponse:
    challenge = get_forecast_challenge(db, challenge_id)
    if challenge is None:
        raise HTTPException(status_code=404, detail="Forecast challenge snapshot not found")
    return challenge


@router.get(
    "/countries/{iso3}/forecast-challenges",
    response_model=list[ForecastChallengeListItem],
    response_model_by_alias=False,
)
def get_country_challenges(iso3: str, db: Session = Depends(get_db)) -> list[ForecastChallengeListItem]:
    try:
        return list_forecast_challenges(db, country_iso3=iso3)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post(
    "/forecast-challenges/{challenge_id}/run-builtins",
    response_model=BuiltInPredictionRunResponse,
    response_model_by_alias=False,
)
def run_challenge_builtin_predictions(
    challenge_id: int,
    payload: BuiltInPredictionRunRequest,
    db: Session = Depends(get_db),
) -> BuiltInPredictionRunResponse:
    try:
        return run_builtin_predictions_for_challenge(
            db,
            challenge_id,
            model_ids=payload.model_ids,
            overwrite_existing=payload.overwrite_existing,
        )
    except ValueError as exc:
        if "not found" in str(exc).lower():
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get(
    "/forecast-challenges/{challenge_id}/predictions",
    response_model=list[PredictionSetResponse],
    response_model_by_alias=False,
)
def get_challenge_predictions(
    challenge_id: int,
    db: Session = Depends(get_db),
) -> list[PredictionSetResponse]:
    if get_forecast_challenge(db, challenge_id) is None:
        raise HTTPException(status_code=404, detail="Forecast challenge snapshot not found")
    return list_prediction_sets(db, challenge_id=challenge_id)


@router.post(
    "/forecast-challenges/{challenge_id}/predictions/upload",
    response_model=ChallengePredictionUploadResult,
    response_model_by_alias=False,
)
async def upload_challenge_prediction_csv(
    challenge_id: int,
    file: UploadFile = File(...),
    model_id: str | None = Form(None),
    model_name: str | None = Form(None),
    unit: str | None = Form(None),
    method_summary: str | None = Form(None, alias="methodSummary"),
    model_url: str | None = Form(None, alias="modelUrl"),
    code_url: str | None = Form(None, alias="codeUrl"),
    submitter_name: str | None = Form(None, alias="submitterName"),
    submitter_email: str | None = Form(None, alias="submitterEmail"),
    organization: str | None = Form(None),
    provenance_url: str | None = Form(None, alias="provenanceUrl"),
    limitations: str | None = Form(None),
    submission_track: str | None = Form(None, alias="submissionTrack"),
    visibility: str | None = Form(None),
    disclosure_notes: str | None = Form(None, alias="disclosureNotes"),
    verified_group: bool = Form(False, alias="verifiedGroup"),
    allow_metric_overlay: bool = Form(False, alias="allowMetricOverlay"),
    db: Session = Depends(get_db),
) -> ChallengePredictionUploadResult:
    try:
        reject_executable_prediction_filename(file.filename)
        content = (await file.read()).decode("utf-8-sig")
        return upload_prediction_csv_for_challenge(
            db,
            challenge_id,
            content,
            model_id=model_id,
            model_name=model_name,
            unit=unit,
            method_summary=method_summary,
            model_url=model_url,
            code_url=code_url,
            submitter_name=submitter_name,
            submitter_email=submitter_email,
            organization=organization,
            provenance_url=provenance_url,
            limitations=limitations,
            submission_track=submission_track,
            visibility=visibility,
            disclosure_notes=disclosure_notes,
            verified_group=verified_group,
            allow_metric_overlay=allow_metric_overlay,
        )
    except NormalizationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except ValueError as exc:
        if "not found" in str(exc).lower():
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post(
    "/forecast-challenges/{challenge_id}/score",
    response_model=ForecastChallengeScoreResponse,
    response_model_by_alias=False,
)
def score_challenge_predictions(
    challenge_id: int,
    payload: ForecastChallengeScoreRequest,
    db: Session = Depends(get_db),
) -> ForecastChallengeScoreResponse:
    try:
        return score_all_prediction_sets_for_challenge(challenge_id, payload.ranking_metric, db)
    except ValueError as exc:
        if "not found" in str(exc).lower():
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get(
    "/forecast-challenges/{challenge_id}/leaderboard",
    response_model=ForecastLeaderboardResponse,
    response_model_by_alias=False,
)
def get_challenge_leaderboard(
    challenge_id: int,
    metric: str = "smape",
    submission_track: str = Query("all", alias="submissionTrack"),
    review_status: str = Query("all", alias="reviewStatus"),
    include_unreviewed: bool = Query(True, alias="includeUnreviewed"),
    db: Session = Depends(get_db),
) -> ForecastLeaderboardResponse:
    try:
        return build_leaderboard(
            challenge_id,
            metric,
            db,
            submission_track=submission_track,
            review_status=review_status,
            include_unreviewed=include_unreviewed,
        )
    except ValueError as exc:
        if "not found" in str(exc).lower():
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get(
    "/forecast-challenges/{challenge_id}/comparison-points",
    response_model=list[ForecastComparisonPointResponse],
    response_model_by_alias=False,
)
def get_challenge_comparison_points(
    challenge_id: int,
    db: Session = Depends(get_db),
) -> list[ForecastComparisonPointResponse]:
    try:
        return build_comparison_points(challenge_id, db)
    except ValueError as exc:
        if "not found" in str(exc).lower():
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get(
    "/prediction-sets",
    response_model=list[PredictionSetResponse],
    response_model_by_alias=False,
)
def get_prediction_sets(
    country_iso3: str | None = Query(None, alias="countryIso3"),
    source_id: str | None = Query(None, alias="sourceId"),
    metric: str | None = None,
    challenge_id: int | None = Query(None, alias="challengeId"),
    db: Session = Depends(get_db),
) -> list[PredictionSetResponse]:
    return list_prediction_sets(
        db,
        challenge_id=challenge_id,
        country_iso3=country_iso3,
        source_id=source_id,
        metric=metric,
    )


@router.get(
    "/prediction-sets/{prediction_set_id}",
    response_model=PredictionSetResponse,
    response_model_by_alias=False,
)
def get_prediction_set_by_id(
    prediction_set_id: int,
    db: Session = Depends(get_db),
) -> PredictionSetResponse:
    prediction_set = get_prediction_set(db, prediction_set_id)
    if prediction_set is None:
        raise HTTPException(status_code=404, detail="Prediction set not found")
    return prediction_set


@router.patch(
    "/prediction-sets/{prediction_set_id}/review",
    response_model=ReviewDecisionResponse,
    response_model_by_alias=False,
)
def review_prediction_set(
    prediction_set_id: int,
    payload: ReviewDecisionRequest,
    db: Session = Depends(get_db),
) -> ReviewDecisionResponse:
    try:
        return apply_review_decision(
            db,
            prediction_set_id,
            review_status=payload.review_status,
            reviewer_name=payload.reviewer_name,
            review_notes=payload.review_notes,
        )
    except ValueError as exc:
        if "not found" in str(exc).lower():
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get(
    "/prediction-sets/{prediction_set_id}/review",
    response_model=ReviewDecisionResponse | None,
    response_model_by_alias=False,
)
def get_prediction_set_review(
    prediction_set_id: int,
    db: Session = Depends(get_db),
) -> ReviewDecisionResponse | None:
    try:
        return get_latest_review_decision(db, prediction_set_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/submitters", response_model=list[SubmitterResponse], response_model_by_alias=False)
def get_submitters(db: Session = Depends(get_db)) -> list[SubmitterResponse]:
    return list_submitters(db)


@router.get("/submitters/{submitter_id}", response_model=SubmitterResponse, response_model_by_alias=False)
def get_submitter_by_id(submitter_id: int, db: Session = Depends(get_db)) -> SubmitterResponse:
    submitter = get_submitter(db, submitter_id)
    if submitter is None:
        raise HTTPException(status_code=404, detail="Submitter not found")
    return submitter


@router.get(
    "/forecast-challenges/{challenge_id}/prediction-template",
    response_model=list[PredictionTemplateRow],
    response_model_by_alias=False,
)
def get_challenge_prediction_template(
    challenge_id: int,
    format: str = "json",
    db: Session = Depends(get_db),
) -> list[PredictionTemplateRow] | Response:
    challenge = get_forecast_challenge(db, challenge_id)
    if challenge is None:
        raise HTTPException(status_code=404, detail="Forecast challenge snapshot not found")
    template = build_prediction_template(challenge)
    if format.lower() == "csv":
        buffer = StringIO()
        fieldnames = [
            "modelId",
            "modelName",
            "targetDate",
            "predictedValue",
            "lower",
            "upper",
            "unit",
            "countryIso3",
            "sourceId",
            "metric",
            "signalCategory",
            "generatedAt",
            "provenanceUrl",
        ]
        writer = csv.DictWriter(buffer, fieldnames=fieldnames)
        writer.writeheader()
        for row in template:
            writer.writerow(
                {
                    "modelId": row.model_id or "",
                    "modelName": row.model_name or "",
                    "targetDate": row.target_date.isoformat(),
                    "predictedValue": "",
                    "lower": "",
                    "upper": "",
                    "unit": row.unit or "",
                    "countryIso3": row.country_iso3,
                    "sourceId": row.source_id,
                    "metric": row.metric,
                    "signalCategory": row.signal_category or "",
                    "generatedAt": "",
                    "provenanceUrl": "",
                }
            )
        return Response(content=buffer.getvalue(), media_type="text/csv")
    return template
