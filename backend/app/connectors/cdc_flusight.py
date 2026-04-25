from app.connectors.base import StaticMetadataConnector


def create_connector() -> StaticMetadataConnector:
    return StaticMetadataConnector(
        source_id="cdc_flusight",
        name="CDC FluSight Forecast Hub",
        category="forecasts_nowcasts",
        publisher="US CDC",
        official_url="https://github.com/cdcepi/FluSight-forecast-hub",
        access_type="public_repository",
        license="See repository license",
        geographic_coverage="United States targets",
        temporal_resolution="weekly",
        update_cadence="forecast-round-dependent",
        reliability_tier="source_provided",
        limitations=[
            "Forecast data are source-provided and target-specific.",
            "Placeholder connector does not fetch live data.",
        ],
        default_coverage_status="partial",
    )

