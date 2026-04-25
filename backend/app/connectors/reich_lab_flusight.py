from app.connectors.base import StaticMetadataConnector


def create_connector() -> StaticMetadataConnector:
    return StaticMetadataConnector(
        source_id="reich_lab_flusight",
        name="Reich Lab FluSight Mirror/Tools",
        category="forecasts_nowcasts",
        publisher="Reich Lab",
        official_url="https://reichlab.io/",
        access_type="public_repository_or_docs",
        license="See source terms",
        geographic_coverage="source-dependent",
        temporal_resolution="weekly/source-dependent",
        update_cadence="source-dependent",
        reliability_tier="source_provided",
        limitations=[
            "This registry entry is a placeholder for future forecast-hub normalization.",
            "No live forecast ingestion is implemented.",
        ],
    )

