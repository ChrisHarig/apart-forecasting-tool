from app.connectors.base import StaticMetadataConnector


def create_connector() -> StaticMetadataConnector:
    return StaticMetadataConnector(
        source_id="ourairports",
        name="OurAirports",
        category="aviation",
        publisher="OurAirports",
        official_url="https://ourairports.com/data/",
        access_type="public_download",
        license="Public domain / see source terms",
        geographic_coverage="global airport metadata",
        temporal_resolution="metadata",
        update_cadence="source-dependent",
        reliability_tier="community_curated",
        limitations=[
            "Airport metadata are not traffic observations.",
            "Placeholder connector does not fetch live data.",
        ],
        default_coverage_status="partial",
    )

