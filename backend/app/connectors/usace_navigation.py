from app.connectors.base import StaticMetadataConnector


def create_connector() -> StaticMetadataConnector:
    return StaticMetadataConnector(
        source_id="usace_navigation",
        name="USACE Navigation Facilities",
        category="maritime_ports_cargo",
        publisher="US Army Corps of Engineers",
        official_url="https://navigation.usace.army.mil/",
        access_type="public_download_or_api",
        license="See source terms",
        geographic_coverage="United States facilities",
        temporal_resolution="metadata/source-dependent",
        update_cadence="source-dependent",
        reliability_tier="official",
        limitations=[
            "Country coverage is primarily United States.",
            "Placeholder connector does not fetch live data.",
        ],
        default_coverage_status="partial",
    )

