"""Normalization helpers for aggregate Sentinel Atlas backend data.

This module is intentionally dependency-light so FastAPI route handlers can call
it before database or connector infrastructure exists. It accepts aggregate
public-health/infrastructure records only and rejects fields that suggest
individual-level, medical-record, or precise personal tracking data.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field, is_dataclass
from datetime import UTC, date, datetime
import csv
from io import StringIO
from math import isfinite
from typing import Any, Mapping, Sequence


AGGREGATE_ONLY_REJECT_FIELDS = frozenset(
    {
        "patient_id",
        "person_id",
        "individual_id",
        "user_id",
        "device_id",
        "imei",
        "imsi",
        "email",
        "phone",
        "phone_number",
        "medical_record_number",
        "mrn",
        "name",
        "full_name",
        "address",
        "home_address",
        "ssn",
        "dob",
        "date_of_birth",
        "license_plate",
    }
)

OPERATIONAL_TRACE_WARNING_FIELDS = frozenset(
    {
        "tail_number",
        "callsign",
        "mmsi",
        "imo",
        "vessel_id",
        "flight_id",
        "vehicle_id",
        "trajectory",
        "raw_trace",
        "gps_trace",
        "contact_trace",
    }
)

COUNTRY_ALIASES = {
    "GLOBAL": "GLOBAL",
    "WORLD": "GLOBAL",
    "US": "USA",
    "USA": "USA",
    "UNITED STATES": "USA",
    "UNITED STATES OF AMERICA": "USA",
    "UK": "GBR",
    "GB": "GBR",
    "GREAT BRITAIN": "GBR",
    "UNITED KINGDOM": "GBR",
}

SOURCE_ID_ALIASES = ("source_id", "sourceId", "source", "sourceIdOrName")
COUNTRY_ALIASES_FIELDS = ("country_iso3", "countryIso3", "iso3", "country", "countryCode")
DATE_ALIASES = ("date", "observed_date", "observedDate", "week_start", "weekStart")
VALUE_ALIASES = ("value", "measurement", "count", "rate", "estimate")
METRIC_ALIASES = ("metric", "measure", "indicator", "signal")


@dataclass(frozen=True)
class Provenance:
    """Source traceability for a normalized aggregate record."""

    source_url: str | None = None
    license: str | None = None
    retrieved_at: date | None = None
    reported_at: date | None = None
    notes: str | None = None
    raw_source: str | None = None


@dataclass(frozen=True)
class NormalizedRecord:
    """Country-scoped aggregate time-series record."""

    source_id: str
    country_iso3: str
    metric: str
    date: date
    value: float
    unit: str | None = None
    admin1: str | None = None
    admin2: str | None = None
    location_name: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    provenance: Provenance = field(default_factory=Provenance)
    reported_at: date | None = None
    ingested_at: date | None = None
    original_fields: tuple[str, ...] = ()


@dataclass(frozen=True)
class SourceDescriptor:
    """Normalized source metadata used by availability and quality scoring."""

    id: str
    name: str
    category: str
    supported_countries: tuple[str, ...] = ()
    reliability_tier: str = "unknown"
    update_cadence: str | None = None
    adapter_status: str | None = None
    provenance_notes: str | None = None
    limitations: tuple[str, ...] = ()
    last_verified_date: date | None = None
    access_type: str | None = None
    user_added: bool = False
    metadata: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class RejectedRecord:
    """A raw record that could not be normalized safely or completely."""

    index: int
    reason: str
    fields: tuple[str, ...]


@dataclass(frozen=True)
class NormalizationResult:
    """Batch normalization output for FastAPI responses or service chaining."""

    records: tuple[NormalizedRecord, ...]
    rejected: tuple[RejectedRecord, ...] = ()
    warnings: tuple[str, ...] = ()


def normalize_iso3(value: Any) -> str | None:
    """Normalize ISO3-like country identifiers.

    Only a small set of common aliases is included. Callers that accept free-form
    country names should resolve them to ISO3 before calling this service.
    """

    if value is None:
        return None
    text = str(value).strip().upper()
    if not text:
        return None
    text = COUNTRY_ALIASES.get(text, text)
    if text == "GLOBAL":
        return text
    if len(text) == 3 and text.isalpha():
        return text
    return None


def normalize_source_descriptor(raw: Mapping[str, Any] | SourceDescriptor) -> SourceDescriptor:
    """Normalize source catalog metadata into a stable service shape."""

    if isinstance(raw, SourceDescriptor):
        return raw

    source_id = _clean_text(_first_value(raw, ("id", "source_id", "sourceId", "name")))
    name = _clean_text(_first_value(raw, ("name", "title", "id"))) or "Unnamed source"
    category = _clean_text(_first_value(raw, ("category", "source_category", "sourceCategory"))) or "unknown"

    countries_raw = _first_value(raw, ("supported_countries", "supportedCountries", "countries", "geographicCoverage"))
    countries = tuple(
        country
        for country in (normalize_iso3(item) for item in _as_sequence(countries_raw))
        if country is not None
    )

    limitations = tuple(
        item for item in (_clean_text(value) for value in _as_sequence(raw.get("limitations"))) if item
    )

    return SourceDescriptor(
        id=source_id or _slugify(name),
        name=name,
        category=category,
        supported_countries=_unique(countries),
        reliability_tier=_clean_text(raw.get("reliability_tier") or raw.get("reliabilityTier")) or "unknown",
        update_cadence=_clean_text(raw.get("update_cadence") or raw.get("updateCadence")),
        adapter_status=_clean_text(raw.get("adapter_status") or raw.get("adapterStatus")),
        provenance_notes=_clean_text(raw.get("provenance_notes") or raw.get("provenanceNotes")),
        limitations=limitations,
        last_verified_date=coerce_date(raw.get("last_verified_date") or raw.get("lastVerifiedDate")),
        access_type=_clean_text(raw.get("access_type") or raw.get("accessType")),
        user_added=bool(raw.get("user_added") or raw.get("userAdded") or False),
        metadata=dict(raw),
    )


def normalize_time_series_records(
    raw_records: Sequence[Mapping[str, Any] | NormalizedRecord],
    *,
    default_source_id: str = "user_upload",
    country_name_to_iso3: Mapping[str, str] | None = None,
) -> NormalizationResult:
    """Normalize raw aggregate records.

    Records missing required country/date/metric/value fields are rejected.
    Records containing individual-level identifiers are rejected. Operational
    trace fields are accepted only as warnings because they must be aggregated
    before use in any route that exposes data to the frontend.
    """

    normalized: list[NormalizedRecord] = []
    rejected: list[RejectedRecord] = []
    warnings: list[str] = []

    for index, raw in enumerate(raw_records):
        if isinstance(raw, NormalizedRecord):
            normalized.append(raw)
            continue

        if not isinstance(raw, Mapping):
            rejected.append(RejectedRecord(index=index, reason="record is not an object", fields=()))
            continue

        field_names = tuple(str(field) for field in raw.keys())
        lower_fields = {_normalize_field_name(field) for field in raw.keys()}

        unsafe_fields = sorted(lower_fields.intersection(AGGREGATE_ONLY_REJECT_FIELDS))
        if unsafe_fields:
            rejected.append(
                RejectedRecord(
                    index=index,
                    reason="record contains individual-level or medical-record fields",
                    fields=tuple(unsafe_fields),
                )
            )
            continue

        trace_fields = sorted(lower_fields.intersection(OPERATIONAL_TRACE_WARNING_FIELDS))
        if trace_fields:
            warnings.append(
                f"Record {index} includes operational trace fields {trace_fields}; only aggregate derivatives should be exposed."
            )

        source_id = _clean_text(_first_value(raw, SOURCE_ID_ALIASES)) or default_source_id
        country = _resolve_country(_first_value(raw, COUNTRY_ALIASES_FIELDS), country_name_to_iso3)
        observed_date = coerce_date(_first_value(raw, DATE_ALIASES))
        metric = _clean_text(_first_value(raw, METRIC_ALIASES))
        value = coerce_float(_first_value(raw, VALUE_ALIASES))

        missing = []
        if not country:
            missing.append("country_iso3")
        if not observed_date:
            missing.append("date")
        if not metric:
            missing.append("metric")
        if value is None:
            missing.append("value")

        if missing:
            rejected.append(
                RejectedRecord(
                    index=index,
                    reason=f"missing or invalid required fields: {', '.join(missing)}",
                    fields=field_names,
                )
            )
            continue

        provenance = _normalize_provenance(raw)
        reported_at = coerce_date(raw.get("reported_at") or raw.get("reportedAt")) or provenance.reported_at

        normalized.append(
            NormalizedRecord(
                source_id=source_id,
                country_iso3=country,
                metric=metric,
                date=observed_date,
                value=value,
                unit=_clean_text(raw.get("unit")),
                admin1=_clean_text(raw.get("admin1")),
                admin2=_clean_text(raw.get("admin2")),
                location_name=_clean_text(raw.get("locationName") or raw.get("location_name")),
                latitude=coerce_float(raw.get("latitude") or raw.get("lat")),
                longitude=coerce_float(raw.get("longitude") or raw.get("lon") or raw.get("lng")),
                provenance=provenance,
                reported_at=reported_at,
                ingested_at=coerce_date(raw.get("ingested_at") or raw.get("ingestedAt")),
                original_fields=field_names,
            )
        )

    return NormalizationResult(
        records=tuple(normalized),
        rejected=tuple(rejected),
        warnings=tuple(_unique(warnings)),
    )


def coerce_date(value: Any) -> date | None:
    """Parse common API date values without guessing missing dates."""

    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    text = str(value).strip()
    if not text:
        return None

    for suffix in ("Z", "+00:00"):
        if text.endswith(suffix):
            text = text[: -len(suffix)]
            break

    try:
        return datetime.fromisoformat(text).date()
    except ValueError:
        pass

    for fmt in ("%Y-%m-%d", "%m/%d/%Y", "%Y/%m/%d", "%Y-%m"):
        try:
            parsed = datetime.strptime(text, fmt)
            return parsed.date()
        except ValueError:
            continue
    return None


def coerce_float(value: Any) -> float | None:
    """Convert finite numeric values and reject NaN/Inf."""

    if value is None or value == "":
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if not isfinite(number):
        return None
    return number


def serializable(value: Any) -> Any:
    """Convert dataclasses and dates into JSON-compatible objects."""

    if is_dataclass(value):
        return serializable(asdict(value))
    if isinstance(value, Mapping):
        return {key: serializable(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return [serializable(item) for item in value]
    if isinstance(value, list):
        return [serializable(item) for item in value]
    if isinstance(value, date):
        return value.isoformat()
    return value


def _normalize_provenance(raw: Mapping[str, Any]) -> Provenance:
    provenance = raw.get("provenance")
    if isinstance(provenance, Mapping):
        source_url = _clean_text(provenance.get("source_url") or provenance.get("sourceUrl") or provenance.get("url"))
        license_value = _clean_text(provenance.get("license"))
        retrieved_at = coerce_date(provenance.get("retrieved_at") or provenance.get("retrievedAt"))
        reported_at = coerce_date(provenance.get("reported_at") or provenance.get("reportedAt"))
        notes = _clean_text(provenance.get("notes"))
        raw_source = _clean_text(provenance.get("raw_source") or provenance.get("rawSource"))
    else:
        source_url = _clean_text(raw.get("source_url") or raw.get("sourceUrl") or raw.get("url"))
        license_value = _clean_text(raw.get("license"))
        retrieved_at = coerce_date(raw.get("retrieved_at") or raw.get("retrievedAt"))
        reported_at = coerce_date(raw.get("reported_at") or raw.get("reportedAt"))
        notes = _clean_text(raw.get("notes") or raw.get("provenance"))
        raw_source = _clean_text(raw.get("raw_source") or raw.get("rawSource"))

    return Provenance(
        source_url=source_url,
        license=license_value,
        retrieved_at=retrieved_at,
        reported_at=reported_at,
        notes=notes,
        raw_source=raw_source,
    )


def _resolve_country(value: Any, country_name_to_iso3: Mapping[str, str] | None) -> str | None:
    iso3 = normalize_iso3(value)
    if iso3:
        return iso3
    if value is None or country_name_to_iso3 is None:
        return None
    mapped = country_name_to_iso3.get(str(value).strip().upper())
    return normalize_iso3(mapped)


def _first_value(raw: Mapping[str, Any], fields: Sequence[str]) -> Any:
    for field_name in fields:
        if field_name in raw and raw[field_name] not in (None, ""):
            return raw[field_name]
    return None


def _clean_text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _as_sequence(value: Any) -> tuple[Any, ...]:
    if value is None or value == "":
        return ()
    if isinstance(value, str):
        return tuple(item.strip() for item in value.split(",") if item.strip())
    if isinstance(value, Sequence):
        return tuple(value)
    return (value,)


def _unique(values: Sequence[Any]) -> tuple[Any, ...]:
    seen = set()
    output = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        output.append(value)
    return tuple(output)


def _normalize_field_name(value: Any) -> str:
    return str(value).strip().lower().replace("-", "_").replace(" ", "_")


def _slugify(value: str) -> str:
    text = "".join(char.lower() if char.isalnum() else "_" for char in value.strip())
    return "_".join(part for part in text.split("_") if part) or "source"


class NormalizationError(ValueError):
    """Raised when an API upload row cannot be safely normalized."""


def parse_csv_observations(content: str) -> list[dict[str, Any]]:
    reader = csv.DictReader(StringIO(content))
    if not reader.fieldnames:
        raise NormalizationError("CSV upload must include a header row")
    return [dict(row) for row in reader]


def normalize_observation_record(
    raw_record: Mapping[str, Any],
    *,
    default_source_id: str | None = None,
    default_country_iso3: str | None = None,
) -> dict[str, Any]:
    """Normalize one API upload row into the SQLAlchemy Observation shape."""

    lower_fields = {_normalize_field_name(field) for field in raw_record.keys()}
    unsafe_fields = sorted(lower_fields.intersection(AGGREGATE_ONLY_REJECT_FIELDS))
    if unsafe_fields:
        raise NormalizationError(
            "Individual-level, PII, medical-record, or precise trace fields are not accepted: "
            + ", ".join(unsafe_fields)
        )
    trace_fields = sorted(lower_fields.intersection(OPERATIONAL_TRACE_WARNING_FIELDS))
    if trace_fields:
        raise NormalizationError(
            "Operational trace-level fields are not accepted in aggregate time-series uploads: "
            + ", ".join(trace_fields)
        )

    source_id = _clean_text(_first_value(raw_record, ("sourceId", "source_id", "source"))) or default_source_id
    country = normalize_iso3(
        _first_value(raw_record, ("countryIso3", "country_iso3", "iso3", "country")) or default_country_iso3
    )
    observed_at = _coerce_datetime(_first_value(raw_record, ("observedAt", "observed_at", "date", "sampleDate")))
    reported_at = _coerce_datetime(_first_value(raw_record, ("reportedAt", "reported_at")))
    signal_category = _canonical_signal_category(
        _first_value(raw_record, ("signalCategory", "signal_category", "category"))
    )
    metric = _clean_text(_first_value(raw_record, ("metric", "measure", "indicator", "signal")))
    value = coerce_float(_first_value(raw_record, ("value", "measurement", "count", "rate", "estimate")))

    missing = []
    if not source_id:
        missing.append("sourceId")
    if not country or country == "GLOBAL":
        missing.append("countryIso3")
    if not observed_at:
        missing.append("observedAt")
    if not signal_category:
        missing.append("signalCategory")
    if not metric:
        missing.append("metric")
    if value is None:
        missing.append("value")
    if missing:
        raise NormalizationError("Missing or invalid required fields: " + ", ".join(missing))

    reporting_lag_days = None
    if reported_at:
        reporting_lag_days = max((reported_at - observed_at).total_seconds() / 86400, 0.0)

    quality_score = coerce_float(_first_value(raw_record, ("qualityScore", "quality_score")))
    if quality_score is not None and not 0 <= quality_score <= 1:
        raise NormalizationError("qualityScore must be between 0 and 1")

    return {
        "source_id": source_id,
        "country_iso3": country,
        "admin1": _clean_text(raw_record.get("admin1")),
        "admin2": _clean_text(raw_record.get("admin2")),
        "location_id": _coerce_int(_first_value(raw_record, ("locationId", "location_id"))),
        "observed_at": observed_at,
        "reported_at": reported_at,
        "signal_category": signal_category,
        "metric": metric,
        "value": value,
        "unit": _clean_text(raw_record.get("unit")),
        "normalized_value": coerce_float(_first_value(raw_record, ("normalizedValue", "normalized_value"))),
        "pathogen": _clean_text(raw_record.get("pathogen")),
        "sample_type": _clean_text(_first_value(raw_record, ("sampleType", "sample_type"))),
        "uncertainty_lower": coerce_float(_first_value(raw_record, ("uncertaintyLower", "uncertainty_lower"))),
        "uncertainty_upper": coerce_float(_first_value(raw_record, ("uncertaintyUpper", "uncertainty_upper"))),
        "reporting_lag_days": reporting_lag_days,
        "quality_score": quality_score,
        "provenance_url": _clean_text(_first_value(raw_record, ("provenanceUrl", "provenance_url", "sourceUrl"))),
        "raw_payload_ref": _clean_text(_first_value(raw_record, ("rawPayloadRef", "raw_payload_ref"))),
    }


def _coerce_datetime(value: Any) -> datetime | None:
    parsed_date = coerce_date(value)
    if parsed_date is None:
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=UTC)
    text = str(value).strip() if value is not None else ""
    if "T" in text:
        if text.endswith("Z"):
            text = text[:-1] + "+00:00"
        try:
            parsed = datetime.fromisoformat(text)
            return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)
        except ValueError:
            pass
    return datetime(parsed_date.year, parsed_date.month, parsed_date.day, tzinfo=UTC)


def _canonical_signal_category(value: Any) -> str | None:
    text = _clean_text(value)
    if not text:
        return None
    normalized = _normalize_field_name(text)
    aliases = {
        "clinical": "clinical_case_hospitalization",
        "case": "clinical_case_hospitalization",
        "cases": "clinical_case_hospitalization",
        "hospitalization": "clinical_case_hospitalization",
        "lab": "pathogen_lab_surveillance",
        "pathogen_surveillance": "pathogen_lab_surveillance",
        "pathogen_lab": "pathogen_lab_surveillance",
        "wastewater": "wastewater",
        "mobility": "mobility",
        "aviation": "aviation",
        "air": "aviation",
        "maritime": "maritime_ports_cargo",
        "ports": "maritime_ports_cargo",
        "ports_maritime_cargo": "maritime_ports_cargo",
        "population": "demographics_population_density",
        "demographics": "demographics_population_density",
        "news": "open_source_news",
        "news_event_surveillance": "open_source_news",
        "forecast": "forecasts_nowcasts",
        "forecasts": "forecasts_nowcasts",
    }
    return aliases.get(normalized, normalized)


def _coerce_int(value: Any) -> int | None:
    if value in (None, ""):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        raise NormalizationError("locationId must be an integer")
