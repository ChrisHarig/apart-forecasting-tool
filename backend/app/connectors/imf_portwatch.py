from app.connectors.base import StaticMetadataConnector


def create_connector() -> StaticMetadataConnector:
    return StaticMetadataConnector(
        source_id="imf_portwatch",
        name="IMF PortWatch",
        category="maritime_ports_cargo",
        publisher="International Monetary Fund",
        official_url="https://portwatch.imf.org/",
        access_type="public_dashboard_or_download",
        license="See source terms",
        geographic_coverage="selected ports and trade flows",
        temporal_resolution="source-dependent",
        update_cadence="source-dependent",
        reliability_tier="source_provided",
        limitations=[
            "Coverage and metrics vary by port and country.",
            "Placeholder connector does not fetch live data.",
        ],
    )

