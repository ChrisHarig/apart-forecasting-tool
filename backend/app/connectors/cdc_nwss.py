from app.connectors.base import StaticMetadataConnector


def create_connector() -> StaticMetadataConnector:
    return StaticMetadataConnector(
        source_id="cdc_nwss",
        name="CDC National Wastewater Surveillance System",
        category="wastewater",
        publisher="US Centers for Disease Control and Prevention",
        official_url="https://www.cdc.gov/nwss/",
        access_type="public_dashboard_or_api",
        license="See source terms",
        geographic_coverage="United States, participating sites",
        temporal_resolution="site-dependent",
        update_cadence="source-dependent",
        reliability_tier="official",
        limitations=[
            "Country coverage is primarily United States.",
            "Placeholder connector does not fetch live data.",
        ],
        default_coverage_status="partial",
    )

