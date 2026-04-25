import re
from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.db import models
from app.schemas.source import DataSourceCreate


def slugify_source_id(value: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9_]+", "_", value.strip().lower()).strip("_")
    return slug or "source"


def ensure_country(db: Session, iso3: str, name: str | None = None) -> models.Country:
    iso3 = iso3.upper()
    country = db.get(models.Country, iso3)
    if country is None:
        country = models.Country(iso3=iso3, name=name or iso3, metadata_json={"createdBy": "backend_stub"})
        db.add(country)
        db.flush()
    return country


def ensure_source(db: Session, source_id: str, *, name: str | None = None, category: str = "teammate_provided_data") -> models.DataSource:
    source = db.get(models.DataSource, source_id)
    if source is None:
        source = models.DataSource(
            id=source_id,
            name=name or source_id,
            category=category,
            adapter_status="manual_or_placeholder",
            reliability_tier="user_provided" if source_id == "user_upload" else "unknown",
            limitations=["Created automatically for aggregate uploaded data."],
            provenance_notes="Source metadata should be completed before production use.",
        )
        db.add(source)
        db.flush()
    return source


def data_source_from_create(payload: DataSourceCreate) -> models.DataSource:
    source_id = payload.id or slugify_source_id(payload.name)
    return models.DataSource(
        id=source_id,
        name=payload.name,
        category=payload.category,
        publisher=payload.publisher,
        official_url=str(payload.official_url) if payload.official_url else None,
        access_type=payload.access_type,
        license=payload.license,
        geographic_coverage=payload.geographic_coverage,
        temporal_resolution=payload.temporal_resolution,
        update_cadence=payload.update_cadence,
        adapter_status=payload.adapter_status,
        reliability_tier=payload.reliability_tier,
        limitations=payload.limitations,
        provenance_notes=payload.provenance_notes,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )

