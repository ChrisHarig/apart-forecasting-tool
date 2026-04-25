from app.connectors.base import StaticMetadataConnector


def create_connector() -> StaticMetadataConnector:
    return StaticMetadataConnector(
        source_id="user_upload",
        name="User-uploaded Aggregate Dataset",
        category="teammate_provided_data",
        publisher="Sentinel Atlas user",
        access_type="manual_upload",
        license="User-provided; must be supplied with upload provenance",
        geographic_coverage="upload-dependent",
        temporal_resolution="upload-dependent",
        update_cadence="manual",
        adapter_status="implemented_manual_upload",
        reliability_tier="user_provided",
        limitations=[
            "Only aggregate, non-PII public-health or infrastructure data are accepted.",
            "Uploads must include provenance or explicitly state provenance is absent.",
        ],
        default_coverage_status="unknown",
    )

