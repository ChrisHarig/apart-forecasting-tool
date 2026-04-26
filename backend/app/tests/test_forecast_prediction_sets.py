from __future__ import annotations

from datetime import date, timedelta
from typing import Any


def _weekly_csv(
    *,
    source_id: str = "fixture_prediction_source",
    country_iso3: str = "USA",
    metric: str = "aggregate_signal",
    count: int = 16,
    start: date = date(2025, 1, 5),
    value_offset: float = 20.0,
) -> tuple[str, bytes]:
    rows = ["sourceId,countryIso3,observedAt,signalCategory,metric,value,unit,provenanceUrl,qualityScore"]
    for index in range(count):
        observed = start + timedelta(days=index * 7)
        value = value_offset + index
        rows.append(
            f"{source_id},{country_iso3},{observed.isoformat()}T00:00:00Z,clinical,{metric},{value},index,https://example.test/{country_iso3}/{metric}/{index},0.9"
        )
    return "prediction-weekly.csv", ("\n".join(rows) + "\n").encode("utf-8")


def _upload(client: Any, content: tuple[str, bytes]) -> None:
    filename, body = content
    response = client.post("/api/timeseries/upload", files={"file": (filename, body, "text/csv")})
    assert response.status_code == 200


def _create_challenge(
    client: Any,
    *,
    mode: str = "prospective_challenge",
    count: int = 16,
    horizon_periods: int = 3,
) -> dict[str, Any]:
    _upload(client, _weekly_csv(count=count))
    response = client.post(
        "/api/forecast-challenges",
        json={
            "mode": mode,
            "countryIso3": "USA",
            "sourceId": "fixture_prediction_source",
            "metric": "aggregate_signal",
            "unit": "index",
            "frequency": "weekly",
            "horizonPeriods": horizon_periods,
        },
    )
    assert response.status_code == 201
    return response.json()


def test_run_builtins_for_prospective_challenge_creates_internal_baseline_prediction_sets(client: Any) -> None:
    challenge = _create_challenge(client)

    response = client.post(
        f"/api/forecast-challenges/{challenge['id']}/run-builtins",
        json={"modelIds": ["naive_last_value", "statsmodels_arima"]},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["challenge_id"] == challenge["id"]
    assert {result["model_id"]: result["status"] for result in body["results"]} == {
        "naive_last_value": "complete",
        "statsmodels_arima": "complete",
    }
    assert len(body["prediction_sets"]) == 2
    for prediction_set in body["prediction_sets"]:
        assert prediction_set["prediction_source"] == "built_in"
        assert prediction_set["submission_track"] == "internal_baseline"
        assert prediction_set["review_status"] == "approved"
        assert prediction_set["validation_status"] == "valid_for_snapshot"
        assert prediction_set["scoring_status"] == "pending_truth"
        assert [point["target_date"] for point in prediction_set["points"]] == challenge["target_dates"]


def test_naive_last_value_predictions_repeat_final_train_value(client: Any) -> None:
    challenge = _create_challenge(client, count=12, horizon_periods=2)

    response = client.post(
        f"/api/forecast-challenges/{challenge['id']}/run-builtins",
        json={"modelIds": ["naive_last_value"]},
    )

    assert response.status_code == 200
    prediction_set = response.json()["prediction_sets"][0]
    predictions = [point["predicted_value"] for point in prediction_set["points"]]
    assert predictions == [31.0, 31.0]
    assert [point["target_date"] for point in prediction_set["points"]] == challenge["target_dates"]


def test_seasonal_naive_returns_insufficient_data_when_cycles_are_insufficient(client: Any) -> None:
    challenge = _create_challenge(client, count=7, horizon_periods=2)

    response = client.post(
        f"/api/forecast-challenges/{challenge['id']}/run-builtins",
        json={"modelIds": ["seasonal_naive"]},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["prediction_sets"] == []
    assert body["results"][0]["status"] == "insufficient_data"
    assert "Need at least 8 training observations" in str(body["results"][0]["warnings"])


def test_arima_and_sarima_use_challenge_target_dates_when_complete(client: Any) -> None:
    challenge = _create_challenge(client, count=16, horizon_periods=3)

    response = client.post(
        f"/api/forecast-challenges/{challenge['id']}/run-builtins",
        json={"modelIds": ["statsmodels_arima", "statsmodels_sarima"]},
    )

    assert response.status_code == 200
    body = response.json()
    statuses = {result["model_id"]: result["status"] for result in body["results"]}
    assert statuses["statsmodels_arima"] == "complete"
    assert statuses["statsmodels_sarima"] in {"complete", "insufficient_data", "failed"}
    for prediction_set in body["prediction_sets"]:
        assert [point["target_date"] for point in prediction_set["points"]] == challenge["target_dates"]


def test_autoets_missing_dependency_returns_model_unavailable_without_crashing(client: Any, monkeypatch: Any) -> None:
    from app.services import forecast_prediction_sets

    challenge = _create_challenge(client)
    monkeypatch.setattr(forecast_prediction_sets, "_dependency_status", lambda _model: "missing_optional_dependency")

    response = client.post(
        f"/api/forecast-challenges/{challenge['id']}/run-builtins",
        json={"modelIds": ["statsforecast_autoets"]},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["prediction_sets"] == []
    assert body["results"][0]["status"] == "model_unavailable"
    assert "statsforecast is not installed" in str(body["results"][0]["warnings"])


def test_existing_builtins_are_not_duplicated_when_overwrite_false(client: Any) -> None:
    challenge = _create_challenge(client)
    payload = {"modelIds": ["naive_last_value"], "overwriteExisting": False}

    first = client.post(f"/api/forecast-challenges/{challenge['id']}/run-builtins", json=payload)
    second = client.post(f"/api/forecast-challenges/{challenge['id']}/run-builtins", json=payload)
    listed = client.get(f"/api/forecast-challenges/{challenge['id']}/predictions")

    assert first.status_code == 200
    assert second.status_code == 200
    assert listed.status_code == 200
    assert len(listed.json()) == 1
    assert second.json()["results"][0]["prediction_set_id"] == first.json()["results"][0]["prediction_set_id"]
    assert "existing_prediction_set" in str(second.json()["results"][0]["warnings"])


def test_overwrite_existing_replaces_builtin_prediction_set_cleanly(client: Any) -> None:
    challenge = _create_challenge(client)
    endpoint = f"/api/forecast-challenges/{challenge['id']}/run-builtins"

    first = client.post(endpoint, json={"modelIds": ["naive_last_value"]})
    second = client.post(endpoint, json={"modelIds": ["naive_last_value"], "overwriteExisting": True})
    listed = client.get(f"/api/forecast-challenges/{challenge['id']}/predictions")

    assert first.status_code == 200
    assert second.status_code == 200
    assert listed.status_code == 200
    assert len(listed.json()) == 1
    assert listed.json()[0]["id"] == second.json()["results"][0]["prediction_set_id"]
    assert listed.json()[0]["model_id"] == "naive_last_value"


def test_prediction_set_list_and_detail_endpoints_return_challenge_predictions(client: Any) -> None:
    challenge = _create_challenge(client)
    run = client.post(
        f"/api/forecast-challenges/{challenge['id']}/run-builtins",
        json={"modelIds": ["naive_last_value"]},
    )
    prediction_set_id = run.json()["results"][0]["prediction_set_id"]

    by_challenge = client.get(f"/api/forecast-challenges/{challenge['id']}/predictions")
    by_query = client.get(
        "/api/prediction-sets?countryIso3=USA&sourceId=fixture_prediction_source&metric=aggregate_signal"
    )
    detail = client.get(f"/api/prediction-sets/{prediction_set_id}")

    assert by_challenge.status_code == 200
    assert by_query.status_code == 200
    assert detail.status_code == 200
    assert [item["id"] for item in by_challenge.json()] == [prediction_set_id]
    assert [item["id"] for item in by_query.json()] == [prediction_set_id]
    assert detail.json()["id"] == prediction_set_id
    assert detail.json()["points"][0]["target_date"] == challenge["target_dates"][0]


def test_running_builtin_predictions_does_not_create_observations(client: Any) -> None:
    challenge = _create_challenge(client, count=12, horizon_periods=2)
    before = client.get(
        "/api/timeseries?countryIso3=USA&sourceId=fixture_prediction_source&metric=aggregate_signal"
    ).json()

    response = client.post(
        f"/api/forecast-challenges/{challenge['id']}/run-builtins",
        json={"modelIds": ["naive_last_value"]},
    )
    after = client.get(
        "/api/timeseries?countryIso3=USA&sourceId=fixture_prediction_source&metric=aggregate_signal"
    ).json()

    assert response.status_code == 200
    assert len(before) == len(after) == 12
