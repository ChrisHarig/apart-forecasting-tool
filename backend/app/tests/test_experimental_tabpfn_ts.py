from __future__ import annotations

from datetime import date, timedelta
from typing import Any


def _weekly_csv(
    *,
    source_id: str = "fixture_tabpfn_source",
    country_iso3: str = "USA",
    metric: str = "aggregate_signal",
    count: int = 22,
    start: date = date(2025, 1, 5),
    value_offset: float = 30.0,
) -> tuple[str, bytes]:
    rows = ["sourceId,countryIso3,observedAt,signalCategory,metric,value,unit,provenanceUrl,qualityScore"]
    for index in range(count):
        observed = start + timedelta(days=index * 7)
        value = value_offset + index
        rows.append(
            f"{source_id},{country_iso3},{observed.isoformat()}T00:00:00Z,clinical,{metric},{value},index,https://example.test/tabpfn/{index},0.9"
        )
    return "tabpfn-weekly.csv", ("\n".join(rows) + "\n").encode("utf-8")


def _upload(client: Any, content: tuple[str, bytes]) -> None:
    filename, body = content
    response = client.post("/api/timeseries/upload", files={"file": (filename, body, "text/csv")})
    assert response.status_code == 200


def _create_prospective_challenge(client: Any, *, count: int = 22, horizon_periods: int = 3) -> dict[str, Any]:
    _upload(client, _weekly_csv(count=count))
    response = client.post(
        "/api/forecast-challenges",
        json={
            "mode": "prospective_challenge",
            "countryIso3": "USA",
            "sourceId": "fixture_tabpfn_source",
            "metric": "aggregate_signal",
            "unit": "index",
            "frequency": "weekly",
            "horizonPeriods": horizon_periods,
        },
    )
    assert response.status_code == 201
    return response.json()


def test_experimental_tabpfn_registry_is_hidden_by_default_and_available_when_requested(client: Any) -> None:
    default_response = client.get("/api/forecast-models")
    experimental_response = client.get("/api/forecast-models?includeExperimental=true")

    assert default_response.status_code == 200
    assert experimental_response.status_code == 200
    assert "experimental_tabpfn_ts" not in {model["id"] for model in default_response.json()}
    assert "experimental_tabpfn_ts" in {model["id"] for model in experimental_response.json()}


def test_experimental_tabpfn_model_detail_returns_safety_metadata(client: Any) -> None:
    response = client.get("/api/forecast-models/experimental_tabpfn_ts")

    assert response.status_code == 200
    body = response.json()
    assert body["id"] == "experimental_tabpfn_ts"
    assert body["display_name"] == "Experimental TabPFN-Time-Series"
    assert body["model_family"] == "foundation_time_series_experimental"
    assert body["status"] == "experimental"
    assert body["experimental"] is True
    assert body["enabled_by_default"] is False
    assert body["feature_flag_enabled"] is False
    assert body["accepts_uploaded_code"] is False
    assert body["benchmark_only"] is True
    assert body["dependency_status"] in {"available", "missing_optional_dependency"}
    assert "not a validated epidemiological model" in " ".join(body["safety_notes"]).lower()
    assert "no remote inference is used by default" in " ".join(body["safety_notes"]).lower()


def test_explicit_experimental_tabpfn_run_returns_disabled_when_feature_flag_false(client: Any) -> None:
    challenge = _create_prospective_challenge(client)

    response = client.post(
        f"/api/forecast-challenges/{challenge['id']}/run-builtins",
        json={"modelIds": ["experimental_tabpfn_ts"]},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["prediction_sets"] == []
    assert body["results"][0]["status"] == "experimental_disabled"
    assert "SENTINEL_ENABLE_EXPERIMENTAL_TABPFN" in str(body["results"][0]["warnings"])


def test_experimental_tabpfn_missing_dependency_is_structured_when_enabled(
    client: Any,
    monkeypatch: Any,
) -> None:
    from app.config import get_settings
    from app.services import forecast_prediction_sets

    challenge = _create_prospective_challenge(client)
    monkeypatch.setenv("SENTINEL_ENABLE_EXPERIMENTAL_TABPFN", "true")
    get_settings.cache_clear()
    monkeypatch.setattr(forecast_prediction_sets, "_dependency_status", lambda _model: "missing_optional_dependency")
    try:
        response = client.post(
            f"/api/forecast-challenges/{challenge['id']}/run-builtins",
            json={"modelIds": ["experimental_tabpfn_ts"]},
        )
    finally:
        get_settings.cache_clear()

    assert response.status_code == 200
    body = response.json()
    assert body["prediction_sets"] == []
    assert body["results"][0]["status"] == "model_unavailable"
    assert "tabpfn-time-series is not installed" in str(body["results"][0]["warnings"])


def test_default_run_builtins_excludes_experimental_tabpfn_and_keeps_naive_working(client: Any) -> None:
    challenge = _create_prospective_challenge(client)

    response = client.post(f"/api/forecast-challenges/{challenge['id']}/run-builtins", json={})

    assert response.status_code == 200
    result_ids = {result["model_id"] for result in response.json()["results"]}
    assert "naive_last_value" in result_ids
    assert "experimental_tabpfn_ts" not in result_ids
    naive = next(result for result in response.json()["results"] if result["model_id"] == "naive_last_value")
    assert naive["status"] == "complete"


def test_experimental_tabpfn_benchmark_preview_returns_disabled_without_creating_predictions(client: Any) -> None:
    _upload(client, _weekly_csv())

    response = client.post(
        "/api/forecast-benchmarks/preview",
        json={
            "countryIso3": "USA",
            "sourceId": "fixture_tabpfn_source",
            "metric": "aggregate_signal",
            "unit": "index",
            "frequency": "weekly",
            "horizonPeriods": 3,
            "modelIds": ["experimental_tabpfn_ts"],
        },
    )

    assert response.status_code == 200
    result = response.json()["results"][0]
    assert result["status"] == "experimental_disabled"
    assert result["points"] == []
    assert "validated" not in response.text.lower() or "not a validated" in response.text.lower()


def test_executable_model_upload_path_is_not_introduced_for_experimental_model(client: Any) -> None:
    response = client.post(
        "/api/forecast-models/predictions/upload",
        files={"file": ("experimental_tabpfn_ts.py", b"print('no execution')", "text/x-python")},
    )

    assert response.status_code == 400
    assert "executable model artifacts are not accepted" in response.json()["detail"].lower()
