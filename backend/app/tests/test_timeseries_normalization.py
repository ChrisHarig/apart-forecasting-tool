from __future__ import annotations

from typing import Any


def test_upload_csv_stores_only_normalized_aggregate_rows(client: Any, aggregate_csv: tuple[str, bytes]) -> None:
    filename, content = aggregate_csv
    response = client.post(
        "/api/timeseries/upload",
        files={"file": (filename, content, "text/csv")},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["inserted_count"] == 6
    assert body["rejected_count"] == 0
    assert len(body["observations"]) == 6
    assert "sourceId,countryIso3" not in response.text

    query = client.get(
        "/api/timeseries",
        params={
            "countryIso3": "USA",
            "sourceId": "fixture_wastewater",
            "metric": "viral_signal",
            "startDate": "2026-04-01T00:00:00Z",
            "endDate": "2026-04-30T00:00:00Z",
        },
    )
    assert query.status_code == 200
    records = query.json()
    assert len(records) == 6
    assert {record["signal_category"] for record in records} == {"wastewater"}


def test_upload_rejects_individual_identifier_fields(client: Any, privacy_risk_csv: tuple[str, bytes]) -> None:
    filename, content = privacy_risk_csv
    response = client.post(
        "/api/timeseries/upload",
        files={"file": (filename, content, "text/csv")},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["inserted_count"] == 0
    assert body["rejected_count"] == 1
    assert "person_id" in body["errors"][0]["error"]
