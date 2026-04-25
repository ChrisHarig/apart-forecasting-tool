from app.connectors.base import StaticMetadataConnector


def create_connector() -> StaticMetadataConnector:
    return StaticMetadataConnector(
        source_id="wastewater_scan",
        name="WastewaterSCAN",
        category="wastewater",
        publisher="WastewaterSCAN",
        official_url="https://data.wastewaterscan.org/",
        access_type="public_dashboard",
        license="See source terms",
        geographic_coverage="selected sites",
        temporal_resolution="site-dependent",
        update_cadence="source-dependent",
        reliability_tier="source_provided",
        limitations=[
            "Coverage is site-based and uneven across countries and subnational regions.",
            "Placeholder connector does not fetch live data.",
        ],
    )

