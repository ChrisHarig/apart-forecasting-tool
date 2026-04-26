from __future__ import annotations

from datetime import date, timedelta
from typing import Any


def _weekly_csv(
    *,
    source_id: str = "fixture_submission_source",
    country_iso3: str = "USA",
    metric: str = "aggregate_signal",
    count: int = 12,
    start: date = date(2025, 1, 5),
) -> tuple[str, bytes]:
    rows = ["sourceId,countryIso3,observedAt,signalCategory,metric,value,unit,provenanceUrl,qualityScore"]
    for index in range(count):
        observed = start + timedelta(days=index * 7)
        rows.append(
            f"{source_id},{country_iso3},{observed.isoformat()}T00:00:00Z,clinical,{metric},{20 + index},index,https://example.test/{index},0.9"
        )
    return "submission-weekly.csv", ("\n".join(rows) + "\n").encode("utf-8")


def _create_challenge(client: Any) -> dict[str, Any]:
    filename, body = _weekly_csv()
    assert client.post("/api/timeseries/upload", files={"file": (filename, body, "text/csv")}).status_code == 200
    response = client.post(
        "/api/forecast-challenges",
        json={
            "mode": "retrospective_holdout",
            "countryIso3": "USA",
            "sourceId": "fixture_submission_source",
            "metric": "aggregate_signal",
            "unit": "index",
            "frequency": "weekly",
            "horizonPeriods": 3,
        },
    )
    assert response.status_code == 201
    return response.json()


def _prediction_csv(challenge: dict[str, Any], *, model_id: str = "team_model") -> tuple[str, bytes]:
    rows = ["modelId,modelName,targetDate,predictedValue,unit"]
    for index, day in enumerate(challenge["target_dates"]):
        rows.append(f"{model_id},Team Model,{day},{29 + index},index")
    return "submission-predictions.csv", ("\n".join(rows) + "\n").encode("utf-8")


def _upload_prediction(
    client: Any,
    challenge: dict[str, Any],
    *,
    model_id: str = "team_model",
    data: dict[str, str] | None = None,
) -> dict[str, Any]:
    filename, body = _prediction_csv(challenge, model_id=model_id)
    response = client.post(
        f"/api/forecast-challenges/{challenge['id']}/predictions/upload",
        data=data or {
            "submitterName": "Public Team",
            "submitterEmail": "team@example.test",
            "organization": "Public Org",
            "methodSummary": "Simple external benchmark predictions.",
            "modelUrl": "https://example.test/model",
            "codeUrl": "https://example.test/code",
        },
        files={"file": (filename, body, "text/csv")},
    )
    assert response.status_code == 200
    return response.json()


def test_public_prediction_upload_requires_submitter_name(client: Any) -> None:
    challenge = _create_challenge(client)
    filename, body = _prediction_csv(challenge)

    response = client.post(
        f"/api/forecast-challenges/{challenge['id']}/predictions/upload",
        data={"methodSummary": "Missing submitter name."},
        files={"file": (filename, body, "text/csv")},
    )

    assert response.status_code == 400
    assert "submitterName is required" in response.json()["detail"]


def test_public_prediction_upload_stores_submitter_metadata_without_leaderboard_email(client: Any) -> None:
    challenge = _create_challenge(client)
    upload = _upload_prediction(client, challenge)

    detail = client.get(f"/api/prediction-sets/{upload['prediction_set_id']}")
    leaderboard = client.get(f"/api/forecast-challenges/{challenge['id']}/leaderboard?metric=smape")
    submitters = client.get("/api/submitters")

    assert detail.status_code == 200
    detail_body = detail.json()
    assert detail_body["submitter_name"] == "Public Team"
    assert detail_body["submitter_email"] is None
    assert detail_body["organization"] == "Public Org"
    assert detail_body["submission_track"] == "public"
    assert detail_body["review_status"] == "unreviewed"
    assert detail_body["method_summary"] == "Simple external benchmark predictions."
    assert detail_body["model_url"] == "https://example.test/model"
    assert detail_body["code_url"] == "https://example.test/code"

    row = leaderboard.json()["leaderboard"][0]
    assert row["submitter_display_name"] == "Public Team"
    assert row["organization"] == "Public Org"
    assert "submitter_email" not in row
    assert submitters.status_code == 200
    assert submitters.json()[0]["display_name"] == "Public Team"
    assert "email" not in submitters.json()[0]


def test_verified_group_upload_can_be_filtered_on_leaderboard(client: Any) -> None:
    challenge = _create_challenge(client)
    _upload_prediction(client, challenge, model_id="public_model")
    _upload_prediction(
        client,
        challenge,
        model_id="verified_model",
        data={
            "submitterName": "Verified Group",
            "organization": "Verified Org",
            "submissionTrack": "verified_group",
            "methodSummary": "Verified group metadata for hackathon demo.",
        },
    )

    leaderboard = client.get(
        f"/api/forecast-challenges/{challenge['id']}/leaderboard?metric=smape&submissionTrack=verified_group"
    )

    assert leaderboard.status_code == 200
    tracks = {row["submission_track"] for row in leaderboard.json()["leaderboard"]}
    assert tracks == {"verified_group"}
    assert leaderboard.json()["leaderboard"][0]["organization"] == "Verified Org"


def test_builtins_remain_internal_baseline_and_approved(client: Any) -> None:
    challenge = _create_challenge(client)
    response = client.post(
        f"/api/forecast-challenges/{challenge['id']}/run-builtins",
        json={"modelIds": ["naive_last_value"]},
    )

    assert response.status_code == 200
    prediction_set = response.json()["prediction_sets"][0]
    assert prediction_set["submission_track"] == "internal_baseline"
    assert prediction_set["review_status"] == "approved"
    assert prediction_set["visibility"] == "public"
    assert prediction_set["verification_status"] == "internal"


def test_leaderboard_can_exclude_unreviewed_and_review_endpoint_approves_or_rejects(client: Any) -> None:
    challenge = _create_challenge(client)
    upload = _upload_prediction(client, challenge)

    excluded = client.get(
        f"/api/forecast-challenges/{challenge['id']}/leaderboard?metric=smape&includeUnreviewed=false"
    )
    assert excluded.status_code == 200
    assert excluded.json()["leaderboard"] == []

    approved = client.patch(
        f"/api/prediction-sets/{upload['prediction_set_id']}/review",
        json={"reviewStatus": "approved", "reviewerName": "Hackathon reviewer", "reviewNotes": "Metadata reviewed."},
    )
    assert approved.status_code == 200
    assert approved.json()["review_status"] == "approved"
    assert client.get(f"/api/prediction-sets/{upload['prediction_set_id']}/review").json()["review_status"] == "approved"

    approved_rows = client.get(
        f"/api/forecast-challenges/{challenge['id']}/leaderboard?metric=smape&reviewStatus=approved"
    )
    assert approved_rows.json()["leaderboard"][0]["review_status"] == "approved"

    rejected = client.patch(
        f"/api/prediction-sets/{upload['prediction_set_id']}/review",
        json={"reviewStatus": "rejected", "reviewerName": "Hackathon reviewer", "reviewNotes": "Rejected for demo."},
    )
    assert rejected.status_code == 200
    filtered = client.get(
        f"/api/forecast-challenges/{challenge['id']}/leaderboard?metric=smape&reviewStatus=approved"
    )
    assert filtered.json()["leaderboard"] == []


def test_model_and_code_urls_are_metadata_only(client: Any) -> None:
    challenge = _create_challenge(client)
    upload = _upload_prediction(
        client,
        challenge,
        model_id="metadata_model",
        data={
            "submitterName": "Metadata Team",
            "methodSummary": "URLs are stored as metadata only.",
            "modelUrl": "https://example.test/metadata-model",
            "codeUrl": "https://example.test/metadata-code",
        },
    )

    detail = client.get(f"/api/prediction-sets/{upload['prediction_set_id']}").json()
    assert detail["model_url"] == "https://example.test/metadata-model"
    assert detail["code_url"] == "https://example.test/metadata-code"
    assert "Executable model artifacts are not accepted" not in str(detail)
