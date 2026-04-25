from __future__ import annotations

from typing import Any


def test_sources_include_placeholder_registry(client: Any) -> None:
    response = client.get("/api/sources")

    assert response.status_code == 200
    sources = response.json()
    source_ids = {source["id"] for source in sources}
    assert {"wastewaterscan", "cdc-nwss", "who-flunet", "user-upload"} <= source_ids
    for source in sources:
        assert set(source) >= {"id", "name", "category", "adapter_status", "reliability_tier", "limitations"}
        assert isinstance(source["limitations"], list)


def test_create_and_patch_source(client: Any) -> None:
    payload = {
        "id": "fixture_source_registry",
        "name": "Fixture Aggregate Source",
        "category": "teammate_provided_data",
        "accessType": "manual_upload",
        "reliabilityTier": "user_provided",
        "limitations": ["Tiny pytest fixture only."],
        "provenanceNotes": "Fixture metadata, not production data.",
    }

    create_response = client.post("/api/sources", json=payload)
    assert create_response.status_code == 201
    assert create_response.json()["id"] == "fixture_source_registry"

    patch_response = client.patch(
        "/api/sources/fixture_source_registry",
        json={"updateCadence": "manual", "license": "fixture only"},
    )
    assert patch_response.status_code == 200
    assert patch_response.json()["update_cadence"] == "manual"
