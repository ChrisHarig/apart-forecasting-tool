from app.connectors.base import StaticMetadataConnector


def create_connector() -> StaticMetadataConnector:
    return StaticMetadataConnector(
        source_id="opensky",
        name="OpenSky Network",
        category="aviation",
        publisher="OpenSky Network",
        official_url="https://opensky-network.org/",
        access_type="api",
        license="See source terms",
        geographic_coverage="ADS-B coverage varies by receiver density",
        temporal_resolution="near-real-time/historical access-dependent",
        update_cadence="access-dependent",
        reliability_tier="third_party",
        limitations=[
            "Coverage is uneven and access terms/rate limits must be respected.",
            "Only aggregate aviation features are in scope; no individual tracking traces.",
            "Placeholder connector does not fetch live data.",
        ],
    )

