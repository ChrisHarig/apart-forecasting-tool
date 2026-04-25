from datetime import date, datetime

from app.schemas.common import APIModel, JsonList


class DataSourceBase(APIModel):
    id: str | None = None
    name: str
    category: str
    publisher: str | None = None
    official_url: str | None = None
    access_type: str | None = None
    license: str | None = None
    geographic_coverage: str | None = None
    temporal_resolution: str | None = None
    update_cadence: str | None = None
    adapter_status: str = "manual"
    reliability_tier: str = "unknown"
    limitations: JsonList = []
    provenance_notes: str | None = None


class DataSourceCreate(DataSourceBase):
    pass


class DataSourcePatch(APIModel):
    name: str | None = None
    category: str | None = None
    publisher: str | None = None
    official_url: str | None = None
    access_type: str | None = None
    license: str | None = None
    geographic_coverage: str | None = None
    temporal_resolution: str | None = None
    update_cadence: str | None = None
    adapter_status: str | None = None
    reliability_tier: str | None = None
    limitations: JsonList | None = None
    provenance_notes: str | None = None


class DataSourceRead(DataSourceBase):
    id: str
    created_at: datetime | None = None
    updated_at: datetime | None = None


class SourceCoverageRead(APIModel):
    id: int | None = None
    source_id: str
    country_iso3: str
    coverage_status: str
    start_date: date | None = None
    end_date: date | None = None
    granularity: str | None = None
    admin_levels_available: JsonList = []
    last_checked_at: datetime | None = None
    notes: str | None = None

