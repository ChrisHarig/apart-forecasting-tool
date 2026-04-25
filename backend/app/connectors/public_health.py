"""Public-health source connector placeholders."""

from __future__ import annotations

from .base import PlaceholderTimeSeriesConnector, source_description

VERIFIED = "2026-04-25"


class WastewaterSCANConnector(PlaceholderTimeSeriesConnector):
    metadata = source_description(
        source_id="wastewaterscan",
        name="WastewaterSCAN",
        category="wastewater",
        owner="WastewaterSCAN",
        official_url="https://data.wastewaterscan.org/",
        description="Wastewater monitoring network for aggregate respiratory and enteric target metrics.",
        geographic_coverage="Primarily United States participating sewersheds",
        supported_countries=("USA",),
        granularity="Site, sewershed, metro aggregation",
        temporal_resolution="Sample date",
        update_cadence="Varies by site",
        likely_fields=("site_id", "sample_date", "target", "normalized_concentration", "trend", "quality_flag"),
        file_formats=("dashboard", "CSV/API TBD"),
        access_type="dashboard_only",
        license_notes="Confirm terms before production ingestion.",
        provenance_notes="Use only aggregate sewershed-level metrics.",
        data_quality_notes="Coverage and reporting lag vary by catchment.",
        limitations="Not all sites report all targets; method and normalization details must be preserved.",
        adapter_status="placeholder",
        country_availability="available",
        last_verified_date=VERIFIED,
        warnings=("Dashboard source only until a permitted data endpoint is confirmed.",),
    )


class CDCNWSSConnector(PlaceholderTimeSeriesConnector):
    metadata = source_description(
        source_id="cdc-nwss",
        name="CDC NWSS / wastewater program",
        category="wastewater",
        owner="CDC",
        official_url="https://www.cdc.gov/nwss/",
        description="CDC National Wastewater Surveillance System public wastewater program and viral activity metrics.",
        geographic_coverage="United States",
        supported_countries=("USA",),
        granularity="Site, county, state, regional summaries where available",
        temporal_resolution="Sample date / reporting week",
        update_cadence="TBD by endpoint and jurisdiction",
        likely_fields=("sample_date", "site", "location", "percentile", "trend", "viral_activity_level"),
        file_formats=("dashboard", "CSV/API TBD"),
        access_type="dashboard_only",
        license_notes="Public CDC source; verify endpoint terms before adapter work.",
        provenance_notes="Primary U.S. wastewater source candidate.",
        data_quality_notes="Public views may be transformed, delayed, or suppressed for coverage reasons.",
        limitations="Not all sites report all targets; historical comparability can vary.",
        adapter_status="placeholder",
        country_availability="available",
        last_verified_date=VERIFIED,
    )


class WHOFluNetConnector(PlaceholderTimeSeriesConnector):
    metadata = source_description(
        source_id="who-flunet",
        name="WHO FluNet",
        category="pathogen_surveillance",
        owner="World Health Organization",
        official_url="https://www.who.int/tools/flunet",
        description="Country-level influenza virological surveillance reports.",
        geographic_coverage="Global country-level reporting",
        supported_countries=("GLOBAL",),
        granularity="Country and week",
        temporal_resolution="Weekly",
        update_cadence="Weekly with reporting delays",
        likely_fields=("country", "week", "specimens_processed", "positive_counts", "subtype"),
        file_formats=("dashboard", "CSV/API TBD"),
        access_type="public_api",
        license_notes="Verify WHO terms and attribution before production use.",
        provenance_notes="Use with clear reporting-delay and completeness metadata.",
        data_quality_notes="Reporting completeness varies by country and week.",
        limitations="Influenza-specific; not comprehensive for all pathogen surveillance.",
        adapter_status="placeholder",
        country_availability="global_source_unknown_country_filter",
        last_verified_date=VERIFIED,
        warnings=("Global metadata exists, but country/week completeness must be reviewed before modeling.",),
    )


class CDCFluSightCurrentConnector(PlaceholderTimeSeriesConnector):
    metadata = source_description(
        source_id="cdc-flusight-current",
        name="CDC FluSight current-week visualization",
        category="forecasts_nowcasts",
        owner="CDC",
        official_url="https://www.cdc.gov/flu/weekly/flusight/",
        description="CDC visualization reference for current-week influenza forecast and nowcast communication.",
        geographic_coverage="United States",
        supported_countries=("USA",),
        granularity="National and jurisdiction-level views where available",
        temporal_resolution="Weekly",
        update_cadence="Weekly when active",
        likely_fields=("reference_date", "target_week", "location", "quantile", "model_output"),
        file_formats=("dashboard", "CSV/API TBD"),
        access_type="dashboard_only",
        license_notes="Public-health government source; verify specific endpoint terms.",
        provenance_notes="Use as a forecast communication reference until direct data adapter exists.",
        data_quality_notes="Forecast challenge scope and targets vary by season.",
        limitations="Dashboard view is not a stable ingestion API.",
        adapter_status="placeholder",
        country_availability="available",
        last_verified_date=VERIFIED,
        model_readiness={
            "status": "not_ready",
            "allowed_use": ["source discovery", "schema planning", "forecast provenance review"],
            "blocked_use": ["production prediction", "automated alerting", "synthetic forecast generation"],
            "requirements_before_modeling": [
                "stable data endpoint",
                "season-specific target documentation",
                "truth data alignment",
                "uncertainty calibration review",
            ],
        },
    )


class CDCFluSightForecastHubConnector(PlaceholderTimeSeriesConnector):
    metadata = source_description(
        source_id="cdc-flusight-hub",
        name="CDC FluSight Forecast Hub",
        category="forecasts_nowcasts",
        owner="CDC / Forecast Hub contributors",
        official_url="https://github.com/cdcepi/FluSight-forecast-hub",
        description="Forecast Hub repository containing influenza challenge submissions and truth data.",
        geographic_coverage="United States",
        supported_countries=("USA",),
        granularity="National and state-level targets depending on season",
        temporal_resolution="Weekly",
        update_cadence="Weekly during challenge periods",
        likely_fields=("model_id", "reference_date", "target", "horizon", "quantile", "location"),
        file_formats=("CSV", "parquet", "GitHub repository"),
        access_type="downloadable_file",
        license_notes="Confirm repository license and attribution before production use.",
        provenance_notes="Model submissions require model identity and reference-date handling.",
        data_quality_notes="Challenge schemas and target definitions can change over time.",
        limitations="Respiratory forecast use case only; not a generalized pandemic feed.",
        adapter_status="partial",
        country_availability="available",
        last_verified_date=VERIFIED,
        model_readiness={
            "status": "requires_review",
            "allowed_use": ["historical benchmark analysis", "schema planning", "forecast provenance review"],
            "blocked_use": ["production prediction", "automated alerting", "synthetic forecast generation"],
            "requirements_before_modeling": [
                "verified hub release/schema",
                "truth data alignment",
                "target and horizon review",
                "model identity and license review",
            ],
        },
    )


class ReichLabFluSightConnector(PlaceholderTimeSeriesConnector):
    metadata = source_description(
        source_id="reich-lab-flusight",
        name="Reich Lab FluSight dashboard",
        category="forecasts_nowcasts",
        owner="Reich Lab",
        official_url="https://reichlab.io/flusight-dashboard/",
        description="Forecast visualization reference for FluSight-style uncertainty and model comparison.",
        geographic_coverage="United States",
        supported_countries=("USA",),
        granularity="National and state-level where available",
        temporal_resolution="Weekly",
        update_cadence="Weekly during active periods",
        likely_fields=("forecast_date", "target", "location", "observed_value", "forecast_quantile"),
        file_formats=("dashboard", "GitHub/data endpoints TBD"),
        access_type="dashboard_only",
        license_notes="Confirm before direct dashboard extraction.",
        provenance_notes="Useful reference for visual design and uncertainty communication.",
        data_quality_notes="Underlying challenge data should be ingested from official hubs where possible.",
        limitations="Not treated as a live data feed in the MVP.",
        adapter_status="placeholder",
        country_availability="available",
        last_verified_date=VERIFIED,
        model_readiness={
            "status": "not_ready",
            "allowed_use": ["source discovery", "visual reference", "uncertainty communication review"],
            "blocked_use": ["production prediction", "automated alerting", "synthetic forecast generation"],
            "requirements_before_modeling": [
                "direct source data agreement or official hub ingestion",
                "truth data alignment",
                "forecast-target documentation",
            ],
        },
    )
