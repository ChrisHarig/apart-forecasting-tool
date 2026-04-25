from datetime import datetime

from app.schemas.common import APIModel, JsonDict


class NewsEventCreate(APIModel):
    country_iso3: str
    event_date: datetime
    headline: str
    summary: str | None = None
    source_name: str
    source_url: str | None = None
    language: str | None = None
    related_pathogen: str | None = None
    signal_category: str = "open_source_news"
    severity: str | None = None
    confidence: float | None = None
    location_name: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    provenance: JsonDict = {}
    deduplication_key: str | None = None


class NewsEventRead(NewsEventCreate):
    id: int
    discovered_at: datetime
    deduplication_key: str

