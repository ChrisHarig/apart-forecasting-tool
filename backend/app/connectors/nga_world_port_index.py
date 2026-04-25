from app.connectors.base import StaticMetadataConnector


def create_connector() -> StaticMetadataConnector:
    return StaticMetadataConnector(
        source_id="nga_world_port_index",
        name="NGA World Port Index",
        category="maritime_ports_cargo",
        publisher="National Geospatial-Intelligence Agency",
        official_url="https://msi.nga.mil/Publications/WPI",
        access_type="public_download",
        license="See source terms",
        geographic_coverage="global port metadata",
        temporal_resolution="metadata",
        update_cadence="source-dependent",
        reliability_tier="official",
        limitations=[
            "Port metadata are not traffic observations.",
            "Placeholder connector does not fetch live data.",
        ],
        default_coverage_status="partial",
    )

