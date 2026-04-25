from app.connectors.base import StaticMetadataConnector


def create_connector() -> StaticMetadataConnector:
    return StaticMetadataConnector(
        source_id="who_flunet",
        name="WHO FluNet",
        category="pathogen_lab_surveillance",
        publisher="World Health Organization",
        official_url="https://www.who.int/tools/flunet",
        access_type="public_download",
        license="See WHO data terms",
        geographic_coverage="country-reported influenza surveillance",
        temporal_resolution="weekly",
        update_cadence="weekly/source-dependent",
        reliability_tier="official",
        limitations=[
            "Reporting completeness varies by country and week.",
            "Placeholder connector does not fetch live data.",
        ],
        default_coverage_status="unknown",
    )

