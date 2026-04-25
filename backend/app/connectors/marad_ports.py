from app.connectors.base import StaticMetadataConnector


def create_connector() -> StaticMetadataConnector:
    return StaticMetadataConnector(
        source_id="marad_ports",
        name="MARAD Principal Ports",
        category="maritime_ports_cargo",
        publisher="US Maritime Administration",
        official_url="https://www.maritime.dot.gov/",
        access_type="public_download",
        license="See source terms",
        geographic_coverage="United States principal port metadata",
        temporal_resolution="metadata",
        update_cadence="source-dependent",
        reliability_tier="official",
        limitations=[
            "Port metadata are not disease or traffic forecasts.",
            "Placeholder connector does not fetch live data.",
        ],
        default_coverage_status="partial",
    )

