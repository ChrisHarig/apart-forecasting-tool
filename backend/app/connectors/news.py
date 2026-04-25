"""News and event surveillance connector placeholders."""

from __future__ import annotations

from .base import PlaceholderNewsConnector, source_description

VERIFIED = "2026-04-25"


class FutureNewsConnector(PlaceholderNewsConnector):
    metadata = source_description(
        source_id="future-news-backend",
        name="Future country news / event surveillance backend",
        category="news_event_surveillance",
        owner="Future backend service",
        official_url="/api/countries/:iso3/news/latest",
        description="Placeholder endpoint for curated country-level public-health news and event surveillance summaries.",
        geographic_coverage="TBD",
        supported_countries=(),
        granularity="Country-level news item or summary",
        temporal_resolution="Publication date",
        update_cadence="TBD",
        likely_fields=("headline", "date", "source", "country", "related_signal", "confidence_status", "url"),
        file_formats=("JSON API",),
        access_type="backend_required",
        license_notes="TBD by backend source agreements.",
        provenance_notes="Frontend must not scrape websites directly.",
        data_quality_notes="Backend should classify source confidence and deduplicate items.",
        limitations="No news feed connected yet.",
        adapter_status="backend_required",
        country_availability="unknown",
        last_verified_date=VERIFIED,
        warnings=(
            "This connector does not scrape websites.",
            "Future ingestion must preserve publisher/source provenance and confidence status.",
        ),
    )
