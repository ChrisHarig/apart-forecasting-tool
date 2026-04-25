from app.connectors.base import StaticMetadataConnector


def create_connector() -> StaticMetadataConnector:
    return StaticMetadataConnector(
        source_id="noaa_ais",
        name="NOAA Marine Cadastre AIS",
        category="maritime_ports_cargo",
        publisher="NOAA Marine Cadastre",
        official_url="https://marinecadastre.gov/ais/",
        access_type="public_download",
        license="See source terms",
        geographic_coverage="United States coastal and inland waters",
        temporal_resolution="source-dependent",
        update_cadence="source-dependent",
        reliability_tier="official",
        limitations=[
            "Only aggregate maritime indicators are in scope for Sentinel Atlas.",
            "Placeholder connector does not fetch live AIS records.",
        ],
        default_coverage_status="partial",
    )

