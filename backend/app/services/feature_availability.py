"""Country and source feature availability for Sentinel Atlas services."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Mapping, Sequence

from .normalization import NormalizedRecord, SourceDescriptor, coerce_date, normalize_iso3, normalize_source_descriptor


FEATURE_FAMILIES = (
    "aggregate_public_health",
    "wastewater",
    "forecast_hub",
    "mobility",
    "news_event",
    "population_context",
    "ports_maritime_context",
)

CATEGORY_TO_FEATURE = {
    "pathogen_surveillance": "aggregate_public_health",
    "public_health": "aggregate_public_health",
    "health_surveillance": "aggregate_public_health",
    "wastewater": "wastewater",
    "forecasts_nowcasts": "forecast_hub",
    "forecast": "forecast_hub",
    "mobility_air_travel": "mobility",
    "mobility": "mobility",
    "news_event_surveillance": "news_event",
    "news": "news_event",
    "event_surveillance": "news_event",
    "population_demographics": "population_context",
    "population": "population_context",
    "ports_maritime_cargo": "ports_maritime_context",
    "maritime": "ports_maritime_context",
}

METRIC_KEYWORDS = {
    "aggregate_public_health": ("case", "ili", "hospital", "death", "positivity", "incidence", "surveillance"),
    "wastewater": ("wastewater", "sewage", "nwss", "viral_load", "copies"),
    "forecast_hub": ("forecast", "nowcast", "hub", "target", "horizon"),
    "mobility": ("mobility", "air", "travel", "flight", "passenger", "origin_destination"),
    "news_event": ("news", "event", "report", "article", "media"),
    "population_context": ("population", "demographic", "census"),
    "ports_maritime_context": ("port", "maritime", "cargo", "ais", "vessel_aggregate"),
}


@dataclass(frozen=True)
class FeatureAvailability:
    """Availability summary for one model-relevant feature family."""

    feature: str
    available: bool
    score: float
    record_count: int = 0
    source_ids: tuple[str, ...] = ()
    latest_date: date | None = None
    country_supported: bool = False
    missing_requirements: tuple[str, ...] = ()
    notes: tuple[str, ...] = ()


@dataclass(frozen=True)
class CountryFeatureAvailability:
    """Country-level feature and source coverage summary."""

    country_iso3: str
    as_of_date: date
    features: Mapping[str, FeatureAvailability] = field(default_factory=dict)
    sources_used: tuple[str, ...] = ()
    supported_source_ids: tuple[str, ...] = ()
    country_coverage_score: float = 0.0
    warnings: tuple[str, ...] = ()


def assess_feature_availability(
    country_iso3: str,
    records: Sequence[NormalizedRecord],
    sources: Sequence[SourceDescriptor | Mapping[str, object]] = (),
    *,
    as_of_date: date | str | None = None,
) -> CountryFeatureAvailability:
    """Assess country/source availability without implying model validity."""

    country = normalize_iso3(country_iso3)
    if not country or country == "GLOBAL":
        raise ValueError("country_iso3 must be a concrete ISO3 country code")

    today = coerce_date(as_of_date) or date.today()
    normalized_sources = tuple(normalize_source_descriptor(source) for source in sources)
    source_by_id = {source.id: source for source in normalized_sources}

    country_records = tuple(record for record in records if record.country_iso3 == country)
    supported_sources = tuple(
        source for source in normalized_sources if source_supports_country(source, country)
    )

    warnings: list[str] = []
    if not country_records:
        warnings.append("No normalized aggregate records are available for this country.")
    if not supported_sources:
        warnings.append("No source metadata explicitly supports this country.")

    feature_map: dict[str, FeatureAvailability] = {}
    for feature in FEATURE_FAMILIES:
        feature_sources = _sources_for_feature(supported_sources, feature)
        feature_records = _records_for_feature(country_records, feature, source_by_id)
        source_ids = _unique(tuple(source.id for source in feature_sources) + tuple(record.source_id for record in feature_records))
        latest = max((record.date for record in feature_records), default=None)
        country_supported = bool(feature_sources or feature_records)
        score = _availability_score(
            has_source=bool(feature_sources),
            record_count=len(feature_records),
            latest_date=latest,
            as_of_date=today,
            provenance_count=_provenance_count(feature_records),
        )

        missing: list[str] = []
        notes: list[str] = []
        if not feature_sources:
            missing.append("country_supported_source")
        if not feature_records:
            missing.append("normalized_aggregate_records")
        if latest is None:
            notes.append("No latest record date because no records are connected.")

        feature_map[feature] = FeatureAvailability(
            feature=feature,
            available=country_supported,
            score=score,
            record_count=len(feature_records),
            source_ids=source_ids,
            latest_date=latest,
            country_supported=country_supported,
            missing_requirements=tuple(missing),
            notes=tuple(notes),
        )

    country_coverage_score = _country_coverage_score(supported_sources, normalized_sources, country_records)
    sources_used = _unique(tuple(record.source_id for record in country_records))

    return CountryFeatureAvailability(
        country_iso3=country,
        as_of_date=today,
        features=feature_map,
        sources_used=sources_used,
        supported_source_ids=tuple(source.id for source in supported_sources),
        country_coverage_score=country_coverage_score,
        warnings=tuple(warnings),
    )


def source_supports_country(source: SourceDescriptor, country_iso3: str) -> bool:
    """Return whether source metadata says a country is supported."""

    country = normalize_iso3(country_iso3)
    if not country:
        return False
    if not source.supported_countries:
        return False
    return "GLOBAL" in source.supported_countries or country in source.supported_countries


def infer_feature_for_source(source: SourceDescriptor) -> str | None:
    category = source.category.strip().lower()
    if category in CATEGORY_TO_FEATURE:
        return CATEGORY_TO_FEATURE[category]

    text = f"{source.id} {source.name} {source.category}".lower()
    for feature, keywords in METRIC_KEYWORDS.items():
        if any(keyword in text for keyword in keywords):
            return feature
    return None


def infer_feature_for_record(record: NormalizedRecord, source: SourceDescriptor | None = None) -> str | None:
    if source is not None:
        feature = infer_feature_for_source(source)
        if feature:
            return feature

    text = f"{record.source_id} {record.metric}".lower()
    for feature, keywords in METRIC_KEYWORDS.items():
        if any(keyword in text for keyword in keywords):
            return feature
    return None


def _sources_for_feature(sources: Sequence[SourceDescriptor], feature: str) -> tuple[SourceDescriptor, ...]:
    return tuple(source for source in sources if infer_feature_for_source(source) == feature)


def _records_for_feature(
    records: Sequence[NormalizedRecord],
    feature: str,
    source_by_id: Mapping[str, SourceDescriptor],
) -> tuple[NormalizedRecord, ...]:
    return tuple(
        record
        for record in records
        if infer_feature_for_record(record, source_by_id.get(record.source_id)) == feature
    )


def _availability_score(
    *,
    has_source: bool,
    record_count: int,
    latest_date: date | None,
    as_of_date: date,
    provenance_count: int,
) -> float:
    source_score = 0.25 if has_source else 0.0
    record_score = min(record_count / 8.0, 1.0) * 0.35
    provenance_score = (provenance_count / record_count * 0.20) if record_count else 0.0
    recency_score = _recency_score(latest_date, as_of_date) * 0.20
    return round(min(source_score + record_score + provenance_score + recency_score, 1.0), 3)


def _recency_score(latest_date: date | None, as_of_date: date) -> float:
    if latest_date is None:
        return 0.0
    age_days = max((as_of_date - latest_date).days, 0)
    if age_days <= 14:
        return 1.0
    if age_days >= 90:
        return 0.0
    return max(0.0, 1.0 - ((age_days - 14) / 76.0))


def _provenance_count(records: Sequence[NormalizedRecord]) -> int:
    return sum(
        1
        for record in records
        if record.provenance.source_url
        or record.provenance.raw_source
        or record.provenance.retrieved_at
        or record.provenance.reported_at
    )


def _country_coverage_score(
    supported_sources: Sequence[SourceDescriptor],
    all_sources: Sequence[SourceDescriptor],
    country_records: Sequence[NormalizedRecord],
) -> float:
    if all_sources:
        metadata_score = len(supported_sources) / len(all_sources)
    else:
        metadata_score = 0.0
    record_score = min(len({record.source_id for record in country_records}) / 3.0, 1.0)
    if not all_sources and country_records:
        return round(record_score * 0.7, 3)
    return round(min((metadata_score * 0.6) + (record_score * 0.4), 1.0), 3)


def _unique(values: Sequence[str]) -> tuple[str, ...]:
    seen: set[str] = set()
    output: list[str] = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        output.append(value)
    return tuple(output)


FEATURE_API_NAMES = {
    "aggregate_public_health": ("clinical_surveillance", "clinical_case_hospitalization"),
    "wastewater": ("wastewater_observations", "wastewater"),
    "forecast_hub": ("forecast_or_nowcast", "forecasts_nowcasts"),
    "mobility": ("mobility_context", "mobility"),
    "news_event": ("news_event_signals", "open_source_news"),
    "population_context": ("demographic_context", "demographics_population_density"),
    "ports_maritime_context": ("maritime_context", "maritime_ports_cargo"),
}


class FeatureAvailabilityService:
    """Database-backed facade used by FastAPI routes."""

    def __init__(self, db) -> None:
        self.db = db

    def compute_features(self, country_iso3: str, window_days: int = 90) -> list[dict]:
        from datetime import UTC, datetime, time

        country = normalize_iso3(country_iso3)
        if not country or country == "GLOBAL":
            return []
        records = _db_records_for_country(self.db, country)
        sources = _db_and_registry_sources(self.db, country)
        availability = assess_feature_availability(country, records, sources)
        output: list[dict] = []
        for feature_name, feature in availability.features.items():
            api_feature_name, signal_category = FEATURE_API_NAMES.get(feature_name, (feature_name, feature_name))
            if not feature.available:
                status = "missing"
            elif feature.record_count == 0:
                status = "partial"
            elif feature.score >= 0.65:
                status = "available"
            else:
                status = "partial"
            latest_observation_at = (
                datetime.combine(feature.latest_date, time.min, tzinfo=UTC) if feature.latest_date else None
            )
            output.append(
                {
                    "country_iso3": country,
                    "as_of_date": availability.as_of_date,
                    "feature_name": api_feature_name,
                    "signal_category": signal_category,
                    "status": status,
                    "source_ids": list(feature.source_ids),
                    "latest_observation_at": latest_observation_at,
                    "coverage_window_days": window_days if feature.record_count else 0,
                    "quality_score": feature.score,
                    "notes": "; ".join(feature.notes or feature.missing_requirements)
                    or "Feature availability is based on source metadata and normalized aggregate observations.",
                }
            )
        return output

    def country_profile(self, country_iso3: str, window_days: int = 90) -> dict:
        country = normalize_iso3(country_iso3) or country_iso3.upper()
        features = self.compute_features(country, window_days=window_days)
        available = [feature for feature in features if feature["status"] in {"available", "partial"}]
        missing = [feature for feature in features if feature["status"] not in {"available", "partial"}]
        quality_scores = [feature["quality_score"] or 0.0 for feature in available]
        readiness = round(sum(quality_scores) / len(quality_scores), 4) if quality_scores else 0.0
        return {
            "country_iso3": country,
            "as_of_date": date.today(),
            "overall_data_readiness_score": readiness,
            "available_signal_categories": [feature["signal_category"] for feature in available],
            "missing_signal_categories": [feature["signal_category"] for feature in missing],
            "features": features,
            "limitations": [
                "Availability is country-specific and source-specific.",
                "Missing, stale, and partial signals are intentionally returned to the frontend.",
            ],
        }


def _db_records_for_country(db, country_iso3: str) -> tuple[NormalizedRecord, ...]:
    from sqlalchemy import select

    from app.db import models
    from app.services.normalization import Provenance

    rows = db.execute(
        select(models.Observation).where(models.Observation.country_iso3 == country_iso3)
    ).scalars().all()
    records: list[NormalizedRecord] = []
    for row in rows:
        observed_date = row.observed_at.date()
        reported_date = row.reported_at.date() if row.reported_at else None
        records.append(
            NormalizedRecord(
                source_id=row.source_id,
                country_iso3=row.country_iso3,
                metric=row.metric,
                date=observed_date,
                value=row.value,
                unit=row.unit,
                admin1=row.admin1,
                admin2=row.admin2,
                provenance=Provenance(source_url=row.provenance_url, reported_at=reported_date),
                reported_at=reported_date,
            )
        )
    return tuple(records)


def _db_and_registry_sources(db, country_iso3: str) -> tuple[SourceDescriptor, ...]:
    from sqlalchemy import select

    from app.db import models
    from app.services.source_registry import get_source_registry

    descriptors: list[SourceDescriptor] = []
    db_sources = db.execute(select(models.DataSource)).scalars().all()
    for source in db_sources:
        supported = [
            row[0]
            for row in db.execute(
                select(models.Observation.country_iso3)
                .where(models.Observation.source_id == source.id)
                .group_by(models.Observation.country_iso3)
            ).all()
        ]
        if country_iso3 not in supported:
            supported.append(country_iso3)
        descriptors.append(
            normalize_source_descriptor(
                {
                    "id": source.id,
                    "name": source.name,
                    "category": source.category,
                    "supported_countries": supported,
                    "reliability_tier": source.reliability_tier,
                    "update_cadence": source.update_cadence,
                    "adapter_status": source.adapter_status,
                    "provenance_notes": source.provenance_notes,
                    "limitations": source.limitations,
                    "access_type": source.access_type,
                }
            )
        )
    for source in get_source_registry().list_source_metadata():
        descriptors.append(normalize_source_descriptor(source))
    return tuple(descriptors)
