from __future__ import annotations

from datetime import date, timedelta
from typing import Any

import pytest


def _weekly_csv(
    *,
    source_id: str = "fixture_forecast_source",
    country_iso3: str = "USA",
    metric: str = "aggregate_signal",
    count: int = 24,
    start: date = date(2025, 1, 5),
    value_offset: float = 10.0,
) -> tuple[str, bytes]:
    rows = ["sourceId,countryIso3,observedAt,signalCategory,metric,value,unit,qualityScore,provenanceUrl"]
    for index in range(count):
        observed = start + timedelta(days=index * 7)
        value = value_offset + index + ((index % 4) * 0.5)
        rows.append(
            f"{source_id},{country_iso3},{observed.isoformat()}T00:00:00Z,clinical,{metric},{value},index,0.9,https://example.test/{country_iso3}/{index}"
        )
    return "weekly.csv", ("\n".join(rows) + "\n").encode("utf-8")


def test_forecast_model_catalog_lists_builtins(client: Any) -> None:
    response = client.get("/api/forecast-models")

    assert response.status_code == 200
    model_ids = {model["id"] for model in response.json()}
    assert {
        "naive_last_value",
        "seasonal_naive",
        "statsmodels_arima",
        "statsmodels_sarima",
        "statsforecast_autoets",
    } <= model_ids


def test_statsforecast_autoets_registry_metadata_includes_safety_notes(client: Any) -> None:
    response = client.get("/api/forecast-models/statsforecast_autoets")

    assert response.status_code == 200
    body = response.json()
    assert body["id"] == "statsforecast_autoets"
    assert body["model_id"] == "statsforecast_autoets"
    assert body["display_name"] == "StatsForecast AutoETS"
    assert body["model_family"] == "exponential_smoothing_ets"
    assert body["implementation_source"] == "statsforecast"
    assert body["benchmark_only"] is True
    assert body["builtin"] is True
    assert body["accepts_uploaded_code"] is False
    assert body["accepts_prediction_csv"] is False
    assert body["dependency_status"] in {"available", "missing_optional_dependency"}
    assert "not an epidemiological model" in " ".join(body["limitations"]).lower()
    assert "uploaded executable model code is never accepted" in " ".join(body["safety_notes"]).lower()


def test_forecast_benchmark_preview_returns_insufficient_data_for_empty_series(client: Any) -> None:
    response = client.post(
        "/api/forecast-benchmarks/preview",
        json={
            "countryIso3": "USA",
            "sourceId": "missing_source",
            "metric": "aggregate_signal",
            "horizonPeriods": 4,
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["output_status"] == "insufficient_data"
    assert body["results"]
    assert {result["status"] for result in body["results"]} == {"insufficient_data"}


def test_valid_observations_can_benchmark_builtin_models(client: Any) -> None:
    filename, content = _weekly_csv()
    upload = client.post("/api/timeseries/upload", files={"file": (filename, content, "text/csv")})
    assert upload.status_code == 200

    response = client.post(
        "/api/forecast-benchmarks/preview",
        json={
            "countryIso3": "USA",
            "sourceId": "fixture_forecast_source",
            "metric": "aggregate_signal",
            "unit": "index",
            "frequency": "weekly",
            "horizonPeriods": 4,
            "modelIds": ["naive_last_value", "seasonal_naive", "statsmodels_arima", "statsmodels_sarima"],
        },
    )

    assert response.status_code == 200
    body = response.json()
    by_model = {result["model_id"]: result for result in body["results"]}
    assert body["output_status"] in {"complete", "partial"}
    assert by_model["naive_last_value"]["status"] == "complete"
    assert by_model["seasonal_naive"]["status"] == "complete"
    assert by_model["statsmodels_arima"]["status"] == "complete"
    assert by_model["statsmodels_sarima"]["status"] == "complete"
    assert by_model["naive_last_value"]["mae"] is not None
    assert len(by_model["statsmodels_arima"]["points"]) == 4
    assert "outbreak" not in response.text.lower()


def test_forecast_benchmark_filters_do_not_leak_other_countries(client: Any) -> None:
    us_filename, us_content = _weekly_csv(country_iso3="USA", count=10, value_offset=10)
    ca_filename, ca_content = _weekly_csv(country_iso3="CAN", count=10, value_offset=1000)
    assert client.post("/api/timeseries/upload", files={"file": (us_filename, us_content, "text/csv")}).status_code == 200
    assert client.post("/api/timeseries/upload", files={"file": (ca_filename, ca_content, "text/csv")}).status_code == 200

    response = client.post(
        "/api/forecast-benchmarks/preview",
        json={
            "countryIso3": "USA",
            "sourceId": "fixture_forecast_source",
            "metric": "aggregate_signal",
            "unit": "index",
            "horizonPeriods": 2,
            "modelIds": ["naive_last_value"],
        },
    )

    assert response.status_code == 200
    points = response.json()["results"][0]["points"]
    assert points
    assert max(point["observed_value"] for point in points) < 100


def test_short_series_marks_arima_models_insufficient_without_failing_run(client: Any) -> None:
    filename, content = _weekly_csv(count=6)
    upload = client.post("/api/timeseries/upload", files={"file": (filename, content, "text/csv")})
    assert upload.status_code == 200

    response = client.post(
        "/api/forecast-benchmarks/preview",
        json={
            "countryIso3": "USA",
            "sourceId": "fixture_forecast_source",
            "metric": "aggregate_signal",
            "unit": "index",
            "horizonPeriods": 2,
            "modelIds": ["naive_last_value", "statsmodels_arima", "statsmodels_sarima"],
        },
    )

    assert response.status_code == 200
    by_model = {result["model_id"]: result for result in response.json()["results"]}
    assert by_model["naive_last_value"]["status"] == "complete"
    assert by_model["statsmodels_arima"]["status"] == "insufficient_data"
    assert by_model["statsmodels_sarima"]["status"] == "insufficient_data"


def test_statsforecast_autoets_returns_insufficient_data_for_short_series(client: Any) -> None:
    filename, content = _weekly_csv(count=6)
    upload = client.post("/api/timeseries/upload", files={"file": (filename, content, "text/csv")})
    assert upload.status_code == 200

    response = client.post(
        "/api/forecast-benchmarks/preview",
        json={
            "countryIso3": "USA",
            "sourceId": "fixture_forecast_source",
            "metric": "aggregate_signal",
            "unit": "index",
            "horizonPeriods": 2,
            "modelIds": ["statsforecast_autoets"],
        },
    )

    assert response.status_code == 200
    result = response.json()["results"][0]
    assert result["model_id"] == "statsforecast_autoets"
    assert result["status"] == "insufficient_data"
    assert result["n_train"] == 4
    assert result["n_test"] == 2


def test_statsforecast_autoets_missing_dependency_is_structured(client: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    from app.services import forecast_benchmark

    original_find_spec = forecast_benchmark.importlib.util.find_spec

    def fake_find_spec(name: str) -> Any:
        if name == "statsforecast":
            return None
        return original_find_spec(name)

    monkeypatch.setattr(forecast_benchmark.importlib.util, "find_spec", fake_find_spec)
    assert client.get("/api/forecast-models/statsforecast_autoets").json()["dependency_status"] == "missing_optional_dependency"

    filename, content = _weekly_csv(count=16)
    upload = client.post("/api/timeseries/upload", files={"file": (filename, content, "text/csv")})
    assert upload.status_code == 200

    response = client.post(
        "/api/forecast-benchmarks/preview",
        json={
            "countryIso3": "USA",
            "sourceId": "fixture_forecast_source",
            "metric": "aggregate_signal",
            "unit": "index",
            "horizonPeriods": 4,
            "modelIds": ["statsforecast_autoets"],
        },
    )

    assert response.status_code == 200
    result = response.json()["results"][0]
    assert result["status"] == "model_unavailable"
    assert "missing_optional_dependency" in str(result["warnings"])


def test_statsforecast_autoets_runs_when_optional_dependency_is_installed(client: Any) -> None:
    pytest.importorskip("statsforecast")
    filename, content = _weekly_csv(count=20)
    upload = client.post("/api/timeseries/upload", files={"file": (filename, content, "text/csv")})
    assert upload.status_code == 200

    response = client.post(
        "/api/forecast-benchmarks/preview",
        json={
            "countryIso3": "USA",
            "sourceId": "fixture_forecast_source",
            "metric": "aggregate_signal",
            "unit": "index",
            "frequency": "weekly",
            "horizonPeriods": 4,
            "modelIds": ["statsforecast_autoets"],
        },
    )

    assert response.status_code == 200
    body = response.json()
    result = body["results"][0]
    assert result["status"] == "complete"
    assert result["mae"] is not None
    assert len(result["points"]) == 4
    assert body["comparison"][0]["model_id"] == "statsforecast_autoets"
    assert "not proof of future public-health validity" in body["comparison"][0]["benchmark_note"]


def test_statsforecast_autoets_does_not_leak_other_country_or_metric(client: Any) -> None:
    pytest.importorskip("statsforecast")
    us_filename, us_content = _weekly_csv(country_iso3="USA", metric="aggregate_signal", count=20, value_offset=10)
    ca_filename, ca_content = _weekly_csv(country_iso3="CAN", metric="aggregate_signal", count=20, value_offset=1000)
    other_filename, other_content = _weekly_csv(country_iso3="USA", metric="other_signal", count=20, value_offset=500)
    assert client.post("/api/timeseries/upload", files={"file": (us_filename, us_content, "text/csv")}).status_code == 200
    assert client.post("/api/timeseries/upload", files={"file": (ca_filename, ca_content, "text/csv")}).status_code == 200
    assert client.post("/api/timeseries/upload", files={"file": (other_filename, other_content, "text/csv")}).status_code == 200

    response = client.post(
        "/api/forecast-benchmarks/preview",
        json={
            "countryIso3": "USA",
            "sourceId": "fixture_forecast_source",
            "metric": "aggregate_signal",
            "unit": "index",
            "horizonPeriods": 4,
            "modelIds": ["statsforecast_autoets"],
        },
    )

    assert response.status_code == 200
    points = response.json()["results"][0]["points"]
    assert points
    assert max(point["observed_value"] for point in points) < 100


def test_uploaded_prediction_csv_can_be_benchmarked_and_fetched(client: Any) -> None:
    filename, content = _weekly_csv(count=8)
    upload = client.post("/api/timeseries/upload", files={"file": (filename, content, "text/csv")})
    assert upload.status_code == 200

    prediction_csv = (
        "modelId,modelName,countryIso3,sourceId,metric,unit,targetDate,predictedValue,lower,upper,provenanceUrl,limitations\n"
        "uploaded_baseline,Uploaded Baseline,USA,fixture_forecast_source,aggregate_signal,index,2025-02-16,16.0,15.0,17.0,https://example.test/model,Test fixture only\n"
        "uploaded_baseline,Uploaded Baseline,USA,fixture_forecast_source,aggregate_signal,index,2025-02-23,17.5,16.0,19.0,https://example.test/model,Test fixture only\n"
    ).encode("utf-8")
    prediction_upload = client.post(
        "/api/forecast-models/predictions/upload",
        files={"file": ("predictions.csv", prediction_csv, "text/csv")},
    )
    assert prediction_upload.status_code == 200
    assert prediction_upload.json()["inserted_count"] == 2

    created = client.post(
        "/api/forecast-benchmarks",
        json={
            "countryIso3": "USA",
            "sourceId": "fixture_forecast_source",
            "metric": "aggregate_signal",
            "unit": "index",
            "horizonPeriods": 2,
            "modelIds": ["uploaded_baseline"],
        },
    )
    assert created.status_code == 201
    created_body = created.json()
    assert created_body["id"]
    assert created_body["results"][0]["status"] == "complete"
    assert created_body["results"][0]["points"][0]["lower"] == 15.0

    fetched = client.get(f"/api/forecast-benchmarks/{created_body['id']}")
    country_runs = client.get("/api/countries/USA/forecast-benchmarks")
    assert fetched.status_code == 200
    assert fetched.json()["id"] == created_body["id"]
    assert country_runs.status_code == 200
    assert [run["id"] for run in country_runs.json()] == [created_body["id"]]


def test_uploaded_prediction_csv_rejects_pii_and_trace_fields(client: Any) -> None:
    prediction_csv = (
        "modelId,modelName,countryIso3,sourceId,metric,targetDate,predictedValue,patient_id,callsign\n"
        "uploaded_bad,Uploaded Bad,USA,fixture_forecast_source,aggregate_signal,2025-02-16,16.0,p-1,ABC123\n"
    ).encode("utf-8")

    response = client.post(
        "/api/forecast-models/predictions/upload",
        files={"file": ("predictions.csv", prediction_csv, "text/csv")},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["inserted_count"] == 0
    assert body["rejected_count"] == 1
    assert "patient_id" in body["errors"][0]["error"]


def test_uploaded_prediction_csv_rejects_executable_artifact_fields(client: Any) -> None:
    prediction_csv = (
        "modelId,modelName,countryIso3,sourceId,metric,targetDate,predictedValue,model_code,shell_command\n"
        "uploaded_bad,Uploaded Bad,USA,fixture_forecast_source,aggregate_signal,2025-02-16,16.0,print('x'),python model.py\n"
    ).encode("utf-8")

    response = client.post(
        "/api/forecast-models/predictions/upload",
        files={"file": ("predictions.csv", prediction_csv, "text/csv")},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["inserted_count"] == 0
    assert body["rejected_count"] == 1
    assert "Executable model artifacts are not accepted" in body["errors"][0]["error"]


def test_executable_model_file_upload_is_rejected(client: Any) -> None:
    response = client.post(
        "/api/forecast-models/predictions/upload",
        files={"file": ("model.py", b"print('do not execute')", "text/x-python")},
    )

    assert response.status_code == 400
    assert "executable model artifacts are not accepted" in response.json()["detail"].lower()


def test_create_forecast_benchmark_rejects_empty_series(client: Any) -> None:
    response = client.post(
        "/api/forecast-benchmarks",
        json={
            "countryIso3": "USA",
            "sourceId": "missing_source",
            "metric": "aggregate_signal",
        },
    )

    assert response.status_code == 400
    assert "No matching stored aggregate observations" in response.json()["detail"]
