from app.connectors.base import StaticMetadataConnector


def create_connector() -> StaticMetadataConnector:
    return StaticMetadataConnector(
        source_id="news_scraper_placeholder",
        name="Future Scraper / Event-Based Surveillance Connector",
        category="open_source_news",
        publisher="Future Sentinel Atlas adapter",
        access_type="planned",
        geographic_coverage="source-dependent",
        temporal_resolution="article/event timestamp",
        update_cadence="planned",
        adapter_status="placeholder",
        reliability_tier="unknown",
        limitations=[
            "Must respect robots.txt, API terms, licenses, and rate limits.",
            "News mentions are not confirmed public-health events.",
            "Placeholder connector does not scrape or fetch live articles.",
        ],
    )

