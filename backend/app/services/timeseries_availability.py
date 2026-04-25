from __future__ import annotations

from collections import defaultdict
from datetime import UTC, datetime
from typing import Iterable

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import models
from app.schemas.observation import TimeSeriesAvailabilityOption, TimeSeriesAvailabilityResponse
from app.services.normalization import normalize_iso3
from app.services.source_registry import get_source_registry


def validate_country_iso3(value: str) -> str:
    iso3 = normalize_iso3(value)
    if not iso3 or iso3 == "GLOBAL":
        raise ValueError("Invalid ISO3 country code")
    return iso3


def get_timeseries_availability(db: Session, country_iso3: str) -> TimeSeriesAvailabilityResponse:
    iso3 = validate_country_iso3(country_iso3)
    observations = (
        db.execute(
            select(models.Observation)
            .where(models.Observation.country_iso3 == iso3)
            .order_by(
                models.Observation.source_id,
                models.Observation.signal_category,
                models.Observation.metric,
                models.Observation.unit,
                models.Observation.observed_at,
                models.Observation.id,
            )
        )
        .scalars()
        .all()
    )

    if not observations:
        return TimeSeriesAvailabilityResponse(country_iso3=iso3, generated_at=datetime.now(UTC), options=[])

    source_ids = {observation.source_id for observation in observations}
    db_sources = {
        source.id: source
        for source in db.execute(select(models.DataSource).where(models.DataSource.id.in_(source_ids))).scalars().all()
    }
    registry_sources = {str(metadata["id"]): metadata for metadata in get_source_registry().list_source_metadata()}

    grouped: dict[tuple[str, str, str, str | None], list[models.Observation]] = defaultdict(list)
    for observation in observations:
        grouped[
            (
                observation.source_id,
                observation.signal_category,
                observation.metric,
                observation.unit,
            )
        ].append(observation)

    options = [
        _availability_option(group, db_sources.get(source_id), registry_sources.get(source_id))
        for (source_id, _signal_category, _metric, _unit), group in grouped.items()
    ]
    options.sort(key=lambda option: (option.source_name.lower(), option.signal_category, option.metric, option.unit or ""))
    return TimeSeriesAvailabilityResponse(country_iso3=iso3, generated_at=datetime.now(UTC), options=options)


def _availability_option(
    observations: list[models.Observation],
    db_source: models.DataSource | None,
    registry_source: dict[str, object] | None,
) -> TimeSeriesAvailabilityOption:
    first = observations[0]
    latest = max(observations, key=lambda observation: (observation.observed_at, observation.id))
    provenance_url = latest.provenance_url or _first_present(observation.provenance_url for observation in reversed(observations))
    warnings: list[dict[str, str]] = []

    if db_source is not None:
        source_name = db_source.name
        limitations = _string_list(db_source.limitations)
    elif registry_source is not None:
        source_name = str(registry_source.get("name") or first.source_id)
        limitations = _string_list(registry_source.get("limitations"))
    else:
        source_name = first.source_id
        limitations = []
        warnings.append(
            {
                "code": "unknown_source",
                "severity": "warning",
                "message": "No source metadata was found for this source_id.",
            }
        )

    if provenance_url is None:
        warnings.append(
            {
                "code": "missing_provenance",
                "severity": "warning",
                "message": "No provenance_url is available for this source/metric option.",
            }
        )

    return TimeSeriesAvailabilityOption(
        source_id=first.source_id,
        source_name=source_name,
        signal_category=first.signal_category,
        metric=first.metric,
        unit=first.unit,
        record_count=len(observations),
        start_date=min(observation.observed_at for observation in observations),
        end_date=max(observation.observed_at for observation in observations),
        latest_observed_at=latest.observed_at,
        latest_value=latest.value,
        quality_score=_quality_score(observations, latest),
        provenance_url=provenance_url,
        limitations=limitations,
        warnings=warnings,
    )


def _quality_score(observations: list[models.Observation], latest: models.Observation) -> float | None:
    if latest.quality_score is not None:
        return latest.quality_score
    values = [observation.quality_score for observation in observations if observation.quality_score is not None]
    if not values:
        return None
    return sum(values) / len(values)


def _first_present(values: Iterable[str | None]) -> str | None:
    for value in values:
        if value:
            return value
    return None


def _string_list(value: object) -> list[str]:
    if value is None or value == "":
        return []
    if isinstance(value, str):
        return [value]
    if isinstance(value, Iterable):
        return [str(item) for item in value if item not in (None, "")]
    return [str(value)]
