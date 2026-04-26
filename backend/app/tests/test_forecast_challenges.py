from __future__ import annotations

from datetime import date, timedelta
from typing import Any


def _weekly_csv(
    *,
    source_id: str = "fixture_challenge_source",
    country_iso3: str = "USA",
    metric: str = "aggregate_signal",
    count: int = 12,
    start: date = date(2025, 1, 5),
    value_offset: float = 10.0,
    include_quality: bool = True,
) -> tuple[str, bytes]:
    quality_column = ",qualityScore" if include_quality else ""
    rows = [f"sourceId,countryIso3,observedAt,signalCategory,metric,value,unit,provenanceUrl{quality_column}"]
    for index in range(count):
        observed = start + timedelta(days=index * 7)
        value = value_offset + index
        quality = ",0.9" if include_quality else ""
        rows.append(
            f"{source_id},{country_iso3},{observed.isoformat()}T00:00:00Z,clinical,{metric},{value},index,https://example.test/{country_iso3}/{metric}/{index}{quality}"
        )
    return "challenge-weekly.csv", ("\n".join(rows) + "\n").encode("utf-8")


def _upload(client: Any, content: tuple[str, bytes]) -> None:
    filename, body = content
    response = client.post("/api/timeseries/upload", files={"file": (filename, body, "text/csv")})
    assert response.status_code == 200


def test_retrospective_challenge_preview_uses_last_n_observations_as_holdout(client: Any) -> None:
    _upload(client, _weekly_csv(count=12))

    response = client.post(
        "/api/forecast-challenges/preview",
        json={
            "mode": "retrospective_holdout",
            "countryIso3": "USA",
            "sourceId": "fixture_challenge_source",
            "metric": "aggregate_signal",
            "unit": "index",
            "frequency": "weekly",
            "horizonPeriods": 3,
        },
    )

    assert response.status_code == 200
    body = response.json()
    snapshot = body["challenge_snapshot"]
    assert snapshot["status"] == "closed"
    assert snapshot["n_train"] == 9
    assert snapshot["n_targets"] == 3
    assert snapshot["target_dates"] == ["2025-03-09", "2025-03-16", "2025-03-23"]
    assert len(snapshot["holdout_observation_ids"]) == 3
    assert [row["target_date"] for row in body["prediction_template"]] == snapshot["target_dates"]


def test_retrospective_prediction_template_does_not_include_holdout_truth(client: Any) -> None:
    _upload(client, _weekly_csv(count=12))

    created = client.post(
        "/api/forecast-challenges",
        json={
            "mode": "retrospective_holdout",
            "countryIso3": "USA",
            "sourceId": "fixture_challenge_source",
            "metric": "aggregate_signal",
            "unit": "index",
            "horizonPeriods": 2,
        },
    )
    assert created.status_code == 201

    template = client.get(f"/api/forecast-challenges/{created.json()['id']}/prediction-template")
    assert template.status_code == 200
    rows = template.json()
    assert rows
    assert all("observed_value" not in row for row in rows)
    assert all(row["predicted_value"] is None for row in rows)


def test_prospective_challenge_preview_generates_future_targets_after_cutoff(client: Any) -> None:
    _upload(client, _weekly_csv(count=12))

    response = client.post(
        "/api/forecast-challenges/preview",
        json={
            "mode": "prospective_challenge",
            "countryIso3": "USA",
            "sourceId": "fixture_challenge_source",
            "metric": "aggregate_signal",
            "unit": "index",
            "frequency": "weekly",
            "horizonPeriods": 3,
            "cutoffAt": "2025-02-23T00:00:00Z",
        },
    )

    assert response.status_code == 200
    snapshot = response.json()["challenge_snapshot"]
    assert snapshot["status"] == "open"
    assert snapshot["train_end"] == "2025-02-23"
    assert snapshot["target_dates"] == ["2025-03-02", "2025-03-09", "2025-03-16"]
    assert snapshot["holdout_observation_ids"] == []
    assert "prospective_truth_unavailable" in str(snapshot["warnings"])


def test_too_short_challenge_series_returns_insufficient_data(client: Any) -> None:
    _upload(client, _weekly_csv(count=5))

    response = client.post(
        "/api/forecast-challenges/preview",
        json={
            "mode": "retrospective_holdout",
            "countryIso3": "USA",
            "sourceId": "fixture_challenge_source",
            "metric": "aggregate_signal",
            "unit": "index",
            "horizonPeriods": 2,
        },
    )

    assert response.status_code == 200
    snapshot = response.json()["challenge_snapshot"]
    assert snapshot["status"] == "insufficient_data"
    assert "insufficient_data" in str(snapshot["warnings"])


def test_challenge_filters_do_not_leak_other_country_or_metric(client: Any) -> None:
    _upload(client, _weekly_csv(country_iso3="USA", metric="aggregate_signal", count=10, value_offset=10))
    _upload(client, _weekly_csv(country_iso3="CAN", metric="aggregate_signal", count=10, value_offset=1000))
    _upload(client, _weekly_csv(country_iso3="USA", metric="other_signal", count=10, value_offset=500))

    response = client.post(
        "/api/forecast-challenges/preview",
        json={
            "mode": "retrospective_holdout",
            "countryIso3": "USA",
            "sourceId": "fixture_challenge_source",
            "metric": "aggregate_signal",
            "unit": "index",
            "horizonPeriods": 2,
        },
    )

    assert response.status_code == 200
    snapshot = response.json()["challenge_snapshot"]
    assert len(snapshot["observation_ids"]) == 10
    assert snapshot["target_dates"] == ["2025-03-02", "2025-03-09"]


def test_challenge_dataset_hash_is_stable_for_same_input(client: Any) -> None:
    _upload(client, _weekly_csv(count=12))
    payload = {
        "mode": "retrospective_holdout",
        "countryIso3": "USA",
        "sourceId": "fixture_challenge_source",
        "metric": "aggregate_signal",
        "unit": "index",
        "horizonPeriods": 3,
    }

    first = client.post("/api/forecast-challenges/preview", json=payload).json()
    second = client.post("/api/forecast-challenges/preview", json=payload).json()

    assert first["challenge_snapshot"]["dataset_hash"] == second["challenge_snapshot"]["dataset_hash"]


def test_persisted_challenge_can_be_retrieved_and_listed_by_country(client: Any) -> None:
    _upload(client, _weekly_csv(count=12))

    created = client.post(
        "/api/forecast-challenges",
        json={
            "mode": "retrospective_holdout",
            "countryIso3": "USA",
            "sourceId": "fixture_challenge_source",
            "metric": "aggregate_signal",
            "unit": "index",
            "horizonPeriods": 2,
        },
    )
    assert created.status_code == 201
    challenge_id = created.json()["id"]

    fetched = client.get(f"/api/forecast-challenges/{challenge_id}")
    all_list = client.get("/api/forecast-challenges?countryIso3=USA")
    country_list = client.get("/api/countries/USA/forecast-challenges")
    other_country_list = client.get("/api/countries/CAN/forecast-challenges")

    assert fetched.status_code == 200
    assert fetched.json()["id"] == challenge_id
    assert all_list.status_code == 200
    assert [item["id"] for item in all_list.json()] == [challenge_id]
    assert country_list.status_code == 200
    assert [item["id"] for item in country_list.json()] == [challenge_id]
    assert other_country_list.status_code == 200
    assert other_country_list.json() == []


def test_challenge_prediction_template_contains_metadata_and_csv_option(client: Any) -> None:
    _upload(client, _weekly_csv(count=12))
    created = client.post(
        "/api/forecast-challenges",
        json={
            "mode": "prospective_challenge",
            "countryIso3": "USA",
            "sourceId": "fixture_challenge_source",
            "metric": "aggregate_signal",
            "signalCategory": "clinical_case_hospitalization",
            "unit": "index",
            "frequency": "weekly",
            "horizonPeriods": 2,
        },
    )
    assert created.status_code == 201
    challenge_id = created.json()["id"]

    json_template = client.get(f"/api/forecast-challenges/{challenge_id}/prediction-template")
    csv_template = client.get(f"/api/forecast-challenges/{challenge_id}/prediction-template?format=csv")

    assert json_template.status_code == 200
    first = json_template.json()[0]
    assert first["country_iso3"] == "USA"
    assert first["source_id"] == "fixture_challenge_source"
    assert first["metric"] == "aggregate_signal"
    assert first["signal_category"] == "clinical_case_hospitalization"
    assert first["unit"] == "index"
    assert first["predicted_value"] is None
    assert csv_template.status_code == 200
    assert "targetDate" in csv_template.text
    assert "predictedValue" in csv_template.text


def test_challenge_creation_does_not_create_fake_observations(client: Any) -> None:
    _upload(client, _weekly_csv(count=12))
    before = client.get(
        "/api/timeseries?countryIso3=USA&sourceId=fixture_challenge_source&metric=aggregate_signal"
    ).json()

    response = client.post(
        "/api/forecast-challenges",
        json={
            "mode": "prospective_challenge",
            "countryIso3": "USA",
            "sourceId": "fixture_challenge_source",
            "metric": "aggregate_signal",
            "unit": "index",
            "horizonPeriods": 4,
        },
    )
    assert response.status_code == 201

    after = client.get(
        "/api/timeseries?countryIso3=USA&sourceId=fixture_challenge_source&metric=aggregate_signal"
    ).json()
    assert len(after) == len(before) == 12
