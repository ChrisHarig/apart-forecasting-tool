from __future__ import annotations

from datetime import date, timedelta
from typing import Any

import pytest

from app.services.forecast_scoring import compute_mae, compute_rmse, compute_smape


def _weekly_csv(
    *,
    source_id: str = "fixture_score_source",
    country_iso3: str = "USA",
    metric: str = "aggregate_signal",
    count: int = 12,
    start: date = date(2025, 1, 5),
    value_offset: float = 20.0,
    unit: str = "index",
) -> tuple[str, bytes]:
    rows = ["sourceId,countryIso3,observedAt,signalCategory,metric,value,unit,provenanceUrl,qualityScore"]
    for index in range(count):
        observed = start + timedelta(days=index * 7)
        value = value_offset + index
        rows.append(
            f"{source_id},{country_iso3},{observed.isoformat()}T00:00:00Z,clinical,{metric},{value},{unit},https://example.test/{country_iso3}/{metric}/{index},0.9"
        )
    return "score-weekly.csv", ("\n".join(rows) + "\n").encode("utf-8")


def _upload_observations(client: Any, content: tuple[str, bytes]) -> None:
    filename, body = content
    response = client.post("/api/timeseries/upload", files={"file": (filename, body, "text/csv")})
    assert response.status_code == 200


def _create_retrospective_challenge(
    client: Any,
    *,
    count: int = 12,
    horizon_periods: int = 3,
    source_id: str = "fixture_score_source",
) -> dict[str, Any]:
    _upload_observations(client, _weekly_csv(count=count, source_id=source_id))
    response = client.post(
        "/api/forecast-challenges",
        json={
            "mode": "retrospective_holdout",
            "countryIso3": "USA",
            "sourceId": source_id,
            "metric": "aggregate_signal",
            "unit": "index",
            "frequency": "weekly",
            "horizonPeriods": horizon_periods,
        },
    )
    assert response.status_code == 201
    return response.json()


def _create_prospective_challenge(
    client: Any,
    *,
    count: int = 8,
    horizon_periods: int = 3,
    source_id: str = "fixture_score_source",
    cutoff_at: str | None = None,
) -> dict[str, Any]:
    _upload_observations(client, _weekly_csv(count=count, source_id=source_id))
    response = client.post(
        "/api/forecast-challenges",
        json={
            "mode": "prospective_challenge",
            "countryIso3": "USA",
            "sourceId": source_id,
            "metric": "aggregate_signal",
            "unit": "index",
            "frequency": "weekly",
            "horizonPeriods": horizon_periods,
            **({"cutoffAt": cutoff_at} if cutoff_at else {}),
        },
    )
    assert response.status_code == 201
    return response.json()


def _prediction_csv(
    challenge: dict[str, Any],
    *,
    model_id: str = "team_model_v1",
    model_name: str = "Team Model v1",
    values: list[float] | None = None,
    country_iso3: str = "USA",
    source_id: str | None = None,
    metric: str = "aggregate_signal",
    unit: str = "index",
    extra_rows: list[str] | None = None,
    extra_header: str = "",
) -> tuple[str, bytes]:
    values = values or [28.0 + index for index, _day in enumerate(challenge["target_dates"])]
    header = "modelId,modelName,countryIso3,sourceId,metric,targetDate,predictedValue,unit,lower,upper" + extra_header
    rows = [header]
    for day, value in zip(challenge["target_dates"], values, strict=False):
        rows.append(
            f"{model_id},{model_name},{country_iso3},{source_id or challenge['source_id']},{metric},{day},{value},{unit},{value - 1},{value + 1}"
        )
    rows.extend(extra_rows or [])
    return "predictions.csv", ("\n".join(rows) + "\n").encode("utf-8")


def _upload_predictions(
    client: Any,
    challenge: dict[str, Any],
    content: tuple[str, bytes],
    *,
    filename: str | None = None,
    data: dict[str, str] | None = None,
) -> Any:
    upload_name, body = content
    return client.post(
        f"/api/forecast-challenges/{challenge['id']}/predictions/upload",
        data=data or {"submitterName": "Team Tester", "methodSummary": "Tiny explicit test fixture."},
        files={"file": (filename or upload_name, body, "text/csv")},
    )


def test_challenge_prediction_upload_creates_prediction_set_and_scores_retrospective(client: Any) -> None:
    challenge = _create_retrospective_challenge(client)
    response = _upload_predictions(client, challenge, _prediction_csv(challenge, values=[28, 31, 30]))

    assert response.status_code == 200
    body = response.json()
    assert body["prediction_set_id"]
    assert body["inserted_count"] == 3
    assert body["validation_status"] == "valid_for_snapshot"
    assert body["scoring_status"] == "scored"

    detail = client.get(f"/api/prediction-sets/{body['prediction_set_id']}")
    assert detail.status_code == 200
    assert detail.json()["prediction_source"] == "user_uploaded"
    assert [point["target_date"] for point in detail.json()["points"]] == challenge["target_dates"]


def test_prediction_upload_rejects_missing_extra_and_duplicate_target_dates(client: Any) -> None:
    challenge = _create_retrospective_challenge(client)
    missing = _prediction_csv(challenge, values=[1, 2])
    extra = _prediction_csv(challenge, extra_rows=["team_model_v1,Team Model v1,USA,fixture_score_source,aggregate_signal,2030-01-01,1,index,0,2"])
    duplicate_day = challenge["target_dates"][0]
    duplicate = _prediction_csv(
        challenge,
        extra_rows=[f"team_model_v1,Team Model v1,USA,fixture_score_source,aggregate_signal,{duplicate_day},1,index,0,2"],
    )

    missing_response = _upload_predictions(client, challenge, missing)
    extra_response = _upload_predictions(client, challenge, extra)
    duplicate_response = _upload_predictions(client, challenge, duplicate)

    assert missing_response.status_code == 200
    assert missing_response.json()["validation_status"] == "invalid"
    assert "missing_target_dates" in str(missing_response.json()["errors"])
    assert extra_response.status_code == 200
    assert extra_response.json()["validation_status"] == "invalid"
    assert "extra_target_dates" in str(extra_response.json()["errors"])
    assert duplicate_response.status_code == 200
    assert duplicate_response.json()["validation_status"] == "invalid"
    assert "duplicate_target_dates" in str(duplicate_response.json()["errors"])


def test_prediction_upload_rejects_wrong_country_source_or_metric_for_scoring(client: Any) -> None:
    challenge = _create_retrospective_challenge(client)

    wrong_country = _upload_predictions(client, challenge, _prediction_csv(challenge, country_iso3="CAN"))
    wrong_source = _upload_predictions(client, challenge, _prediction_csv(challenge, source_id="other_source"))
    wrong_metric = _upload_predictions(client, challenge, _prediction_csv(challenge, metric="other_metric"))

    assert wrong_country.json()["validation_status"] == "invalid"
    assert "wrong_country" in str(wrong_country.json()["errors"])
    assert wrong_source.json()["validation_status"] == "invalid"
    assert "wrong_source" in str(wrong_source.json()["errors"])
    assert wrong_metric.json()["validation_status"] == "invalid"
    assert "wrong_metric" in str(wrong_metric.json()["errors"])


def test_unit_mismatch_is_overlay_only_and_not_scored(client: Any) -> None:
    challenge = _create_retrospective_challenge(client)
    response = _upload_predictions(client, challenge, _prediction_csv(challenge, unit="other_unit"))

    assert response.status_code == 200
    body = response.json()
    assert body["validation_status"] == "overlay_only"
    assert body["scoring_status"] == "unscored"
    assert body["prediction_set_id"]

    score = client.post(f"/api/forecast-challenges/{challenge['id']}/score", json={"rankingMetric": "smape"})
    leaderboard = client.get(f"/api/forecast-challenges/{challenge['id']}/leaderboard?metric=smape")
    assert score.status_code == 200
    assert leaderboard.status_code == 200
    assert leaderboard.json()["leaderboard"][0]["status"] == "overlay_only"
    assert leaderboard.json()["leaderboard"][0]["rank"] is None


def test_prediction_upload_rejects_executable_and_pii_fields(client: Any) -> None:
    challenge = _create_retrospective_challenge(client)
    executable = _upload_predictions(client, challenge, _prediction_csv(challenge), filename="model.py")
    pii = _prediction_csv(challenge, extra_header=",email")
    pii_response = _upload_predictions(client, challenge, pii)

    assert executable.status_code == 400
    assert "Executable model artifacts are not accepted" in executable.text
    assert pii_response.status_code == 200
    assert pii_response.json()["validation_status"] == "invalid"
    assert "PII" in str(pii_response.json()["errors"])


def test_prospective_scoring_transitions_pending_partial_and_scored(client: Any) -> None:
    pending = _create_prospective_challenge(client, count=8, horizon_periods=3, source_id="fixture_score_pending")
    pending_upload = _upload_predictions(client, pending, _prediction_csv(pending, values=[28, 29, 30]))
    assert pending_upload.json()["scoring_status"] == "pending_truth"
    pending_score = client.post(f"/api/forecast-challenges/{pending['id']}/score", json={"rankingMetric": "smape"})
    assert pending_score.json()["status"] == "pending_truth"

    partial = _create_prospective_challenge(
        client,
        count=9,
        horizon_periods=3,
        source_id="fixture_score_partial",
        cutoff_at="2025-02-23T00:00:00Z",
    )
    partial_upload = _upload_predictions(client, partial, _prediction_csv(partial, values=[28, 29, 30]))
    partial_score = client.post(f"/api/forecast-challenges/{partial['id']}/score", json={"rankingMetric": "smape"})
    assert partial_upload.json()["scoring_status"] == "partially_scored"
    assert partial_score.json()["status"] == "partially_scored"

    full = _create_prospective_challenge(
        client,
        count=11,
        horizon_periods=3,
        source_id="fixture_score_full",
        cutoff_at="2025-02-23T00:00:00Z",
    )
    full_upload = _upload_predictions(client, full, _prediction_csv(full, values=[28, 29, 30]))
    full_score = client.post(f"/api/forecast-challenges/{full['id']}/score", json={"rankingMetric": "smape"})
    assert full_upload.json()["scoring_status"] == "scored"
    assert full_score.json()["status"] == "scored"


def test_metric_calculation_helpers_handle_expected_values_and_zero_smape() -> None:
    points = [(10.0, 8.0), (20.0, 22.0)]
    assert compute_mae(points) == pytest.approx(2.0)
    assert compute_rmse(points) == pytest.approx(2.0)
    assert compute_smape([(0.0, 0.0), (10.0, 5.0)]) == pytest.approx(33.3333333333)


def test_leaderboard_ranks_by_selected_metric_and_comparison_points_include_predictions(client: Any) -> None:
    challenge = _create_retrospective_challenge(client)
    better = _prediction_csv(challenge, model_id="team_better", model_name="Team Better", values=[29, 30, 31])
    worse = _prediction_csv(challenge, model_id="team_worse", model_name="Team Worse", values=[20, 20, 20])
    _upload_predictions(client, challenge, better)
    _upload_predictions(client, challenge, worse)

    score = client.post(f"/api/forecast-challenges/{challenge['id']}/score", json={"rankingMetric": "rmse"})
    leaderboard = client.get(f"/api/forecast-challenges/{challenge['id']}/leaderboard?metric=rmse")
    comparison = client.get(f"/api/forecast-challenges/{challenge['id']}/comparison-points")

    assert score.status_code == 200
    assert leaderboard.status_code == 200
    assert leaderboard.json()["ranking_metric"] == "rmse"
    assert leaderboard.json()["leaderboard"][0]["model_id"] == "team_better"
    assert leaderboard.json()["leaderboard"][0]["rank"] == 1
    assert comparison.status_code == 200
    assert comparison.json()[0]["observed_value"] == 29.0
    assert {item["model_id"] for item in comparison.json()[0]["predictions"]} == {"team_better", "team_worse"}


def test_built_in_and_user_uploaded_prediction_sets_are_scored_through_same_path(client: Any) -> None:
    challenge = _create_retrospective_challenge(client)
    builtin = client.post(
        f"/api/forecast-challenges/{challenge['id']}/run-builtins",
        json={"modelIds": ["naive_last_value"]},
    )
    uploaded = _upload_predictions(client, challenge, _prediction_csv(challenge, model_id="team_model", values=[29, 30, 31]))
    score = client.post(f"/api/forecast-challenges/{challenge['id']}/score", json={"rankingMetric": "smape"})
    leaderboard = client.get(f"/api/forecast-challenges/{challenge['id']}/leaderboard?metric=smape")

    assert builtin.status_code == 200
    assert uploaded.status_code == 200
    assert score.status_code == 200
    entries = leaderboard.json()["leaderboard"]
    assert {entry["prediction_source"] for entry in entries} == {"built_in", "user_uploaded"}
    assert all(entry["status"] == "scored" for entry in entries)
