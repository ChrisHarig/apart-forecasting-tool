from __future__ import annotations

from typing import Any


def test_country_features_show_missingness_and_uploaded_signal(
    client: Any,
    aggregate_csv: tuple[str, bytes],
) -> None:
    filename, content = aggregate_csv
    client.post("/api/timeseries/upload", files={"file": (filename, content, "text/csv")})

    response = client.get("/api/countries/USA/features")

    assert response.status_code == 200
    features = response.json()
    by_feature = {feature["feature_name"]: feature for feature in features}
    assert by_feature["wastewater_observations"]["status"] in {"available", "partial"}
    assert "fixture_wastewater" in by_feature["wastewater_observations"]["source_ids"]
    assert by_feature["clinical_surveillance"]["status"] in {"missing", "unknown", "stale", "partial"}


def test_hover_news_endpoint_empty_state_is_valid(client: Any) -> None:
    response = client.get("/api/countries/USA/news/latest")

    assert response.status_code == 200
    assert response.json() == []
