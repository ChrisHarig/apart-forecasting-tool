from __future__ import annotations

from typing import Any


def test_model_preview_refuses_to_fabricate_without_data(client: Any) -> None:
    response = client.post(
        "/api/model-runs/preview",
        json={"countryIso3": "CAN", "horizonDays": 14, "targetSignal": "public_health_signal"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["selected_model_id"] == "insufficient_data"
    assert body["output_status"] == "insufficient_data"
    assert "fabricate" in " ".join(str(warning).lower() for warning in body["warnings"])


def test_model_run_uses_uploaded_wastewater_only_for_trend_summary(
    client: Any,
    aggregate_csv: tuple[str, bytes],
) -> None:
    filename, content = aggregate_csv
    client.post("/api/timeseries/upload", files={"file": (filename, content, "text/csv")})

    response = client.post(
        "/api/model-runs",
        json={"countryIso3": "USA", "horizonDays": 14, "targetSignal": "wastewater"},
    )

    assert response.status_code == 201
    body = response.json()
    assert body["selected_model_id"] == "wastewater_trend_only"
    assert body["output_status"] in {"complete", "partial"}
    assert body["output_points"]
    assert body["output_points"][0]["metric"] == "observed_wastewater_relative_change"
    assert "not a validated outbreak prediction" in body["explanation"].lower()

