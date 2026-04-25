from __future__ import annotations

from typing import Any


def test_country_timeseries_availability_empty_when_no_observations(client: Any) -> None:
    response = client.get("/api/countries/USA/timeseries/available")

    assert response.status_code == 200
    body = response.json()
    assert body["country_iso3"] == "USA"
    assert body["options"] == []
    assert body["warnings"] == []
    assert body["limitations"] == []


def test_country_timeseries_availability_summarizes_uploaded_observations(
    client: Any,
    aggregate_csv: tuple[str, bytes],
) -> None:
    filename, content = aggregate_csv
    upload = client.post("/api/timeseries/upload", files={"file": (filename, content, "text/csv")})
    assert upload.status_code == 200

    response = client.get("/api/countries/USA/timeseries/available")

    assert response.status_code == 200
    body = response.json()
    assert body["country_iso3"] == "USA"
    assert len(body["options"]) == 1
    option = body["options"][0]
    assert option["source_id"] == "fixture_wastewater"
    assert option["source_name"] == "fixture_wastewater"
    assert option["signal_category"] == "wastewater"
    assert option["metric"] == "viral_signal"
    assert option["unit"] == "copies_ml"
    assert option["record_count"] == 6
    assert option["start_date"].startswith("2026-04-01T00:00:00")
    assert option["end_date"].startswith("2026-04-22T00:00:00")
    assert option["latest_observed_at"].startswith("2026-04-22T00:00:00")
    assert option["latest_value"] == 20
    assert option["quality_score"] == 0.84
    assert option["provenance_url"] == "https://example.test/f"
    assert option["warnings"] == []


def test_timeseries_availability_alias_matches_country_endpoint(
    client: Any,
    aggregate_csv: tuple[str, bytes],
) -> None:
    filename, content = aggregate_csv
    upload = client.post("/api/timeseries/upload", files={"file": (filename, content, "text/csv")})
    assert upload.status_code == 200

    response = client.get("/api/timeseries/available", params={"countryIso3": "USA"})

    assert response.status_code == 200
    body = response.json()
    assert body["country_iso3"] == "USA"
    assert body["options"][0]["source_id"] == "fixture_wastewater"
    assert body["options"][0]["record_count"] == 6


def test_country_timeseries_availability_does_not_leak_other_countries(client: Any) -> None:
    content = (
        "sourceId,countryIso3,observedAt,signalCategory,metric,value,unit,qualityScore,provenanceUrl\n"
        "fixture_wastewater,USA,2026-04-01T00:00:00Z,wastewater,viral_signal,10,copies_ml,0.7,https://example.test/us\n"
        "fixture_wastewater,CAN,2026-04-01T00:00:00Z,wastewater,viral_signal,99,copies_ml,0.7,https://example.test/ca\n"
    ).encode("utf-8")
    upload = client.post("/api/timeseries/upload", files={"file": ("mixed.csv", content, "text/csv")})
    assert upload.status_code == 200

    response = client.get("/api/countries/USA/timeseries/available")

    assert response.status_code == 200
    options = response.json()["options"]
    assert len(options) == 1
    assert options[0]["record_count"] == 1
    assert options[0]["latest_value"] == 10


def test_timeseries_fetch_filters_match_availability_options(client: Any) -> None:
    content = (
        "sourceId,countryIso3,observedAt,signalCategory,metric,value,unit\n"
        "fixture_wastewater,USA,2026-04-01T00:00:00Z,wastewater,viral_signal,10,copies_ml\n"
        "fixture_wastewater,USA,2026-04-05T00:00:00Z,wastewater,viral_signal,12,copies_ml\n"
        "fixture_wastewater,USA,2026-04-09T00:00:00Z,wastewater,viral_signal,13,copies_ml\n"
        "fixture_wastewater,USA,2026-04-09T00:00:00Z,wastewater,other_metric,999,copies_ml\n"
        "other_source,USA,2026-04-09T00:00:00Z,wastewater,viral_signal,888,copies_ml\n"
        "fixture_wastewater,CAN,2026-04-09T00:00:00Z,wastewater,viral_signal,777,copies_ml\n"
    ).encode("utf-8")
    upload = client.post("/api/timeseries/upload", files={"file": ("filters.csv", content, "text/csv")})
    assert upload.status_code == 200

    response = client.get(
        "/api/timeseries",
        params={
            "countryIso3": "USA",
            "sourceId": "fixture_wastewater",
            "metric": "viral_signal",
            "startDate": "2026-04-05T00:00:00Z",
            "endDate": "2026-04-09T00:00:00Z",
        },
    )

    assert response.status_code == 200
    records = response.json()
    assert [record["value"] for record in records] == [12, 13]
    assert {record["country_iso3"] for record in records} == {"USA"}
    assert {record["source_id"] for record in records} == {"fixture_wastewater"}
    assert {record["metric"] for record in records} == {"viral_signal"}


def test_invalid_iso3_returns_validation_error(client: Any) -> None:
    response = client.get("/api/countries/USAA/timeseries/available")

    assert response.status_code == 422
    assert "Invalid ISO3" in response.json()["detail"]


def test_upload_rejects_operational_trace_fields(client: Any) -> None:
    content = (
        "sourceId,countryIso3,observedAt,signalCategory,metric,value,callsign\n"
        "fixture_aviation,USA,2026-04-01T00:00:00Z,aviation,aggregate_arrivals,10,ABC123\n"
    ).encode("utf-8")

    response = client.post("/api/timeseries/upload", files={"file": ("trace.csv", content, "text/csv")})

    assert response.status_code == 200
    body = response.json()
    assert body["inserted_count"] == 0
    assert body["rejected_count"] == 1
    assert "callsign" in body["errors"][0]["error"]


def test_usa_default_country_endpoints_work_empty(client: Any) -> None:
    country = client.get("/api/countries/USA")
    sources = client.get("/api/countries/USA/sources")
    availability = client.get("/api/countries/USA/timeseries/available")
    news = client.get("/api/countries/USA/news/latest")

    assert country.status_code == 200
    assert country.json()["iso3"] == "USA"
    assert sources.status_code == 200
    assert isinstance(sources.json(), list)
    assert availability.status_code == 200
    assert availability.json()["options"] == []
    assert news.status_code == 200
    assert news.json() == []
