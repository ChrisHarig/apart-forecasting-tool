"""Connector contracts for Sentinel Atlas aggregate data sources.

The backend connector layer is deliberately conservative: source metadata and
country availability can be exposed before ingestion exists, but observations
must come only from real, provenance-carrying aggregate records.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import asdict, dataclass, field
from datetime import date, datetime, timezone
from typing import Any, Iterable, Literal, Mapping, Sequence

ConnectorKind = Literal["source_metadata", "time_series", "geospatial", "news"]
AvailabilityStatus = Literal["partial", "unknown", "unavailable"]
ValidationSeverity = Literal["error", "warning"]


SAFE_AGGREGATE_FIELDS = {
    "admin1",
    "admin2",
    "capacity",
    "confidence_status",
    "country",
    "country_iso3",
    "date",
    "description",
    "facility_id",
    "facility_name",
    "geography_id",
    "geography_name",
    "headline",
    "iata",
    "icao",
    "imports",
    "iso3",
    "latitude",
    "location_id",
    "location_name",
    "longitude",
    "metric",
    "name",
    "notes",
    "observed_value",
    "owner",
    "port_code",
    "port_name",
    "portcalls",
    "provenance",
    "publication_date",
    "quality",
    "quality_flag",
    "reference_date",
    "related_signal",
    "sample_date",
    "series_key",
    "series_label",
    "severity",
    "source",
    "source_id",
    "source_url",
    "target",
    "temporal_resolution",
    "unit",
    "update_cadence",
    "url",
    "value",
    "vessel_type",
    "week",
}

SENSITIVE_OR_TRACE_FIELDS = {
    "address",
    "advertising_id",
    "base_datetime",
    "basedatetime",
    "callsign",
    "device_id",
    "email",
    "flight_id",
    "full_name",
    "icao24",
    "imei",
    "imsi",
    "imo",
    "individual_id",
    "ip_address",
    "mmsi",
    "patient_id",
    "patient_name",
    "person_id",
    "person_name",
    "phone",
    "raw_latitude",
    "raw_longitude",
    "tail_number",
    "timestamp",
    "vessel_id",
}

MODEL_READINESS_PLACEHOLDER = {
    "status": "metadata_only",
    "allowed_use": [
        "source discovery",
        "provenance review",
        "country coverage scoping",
        "schema planning",
    ],
    "blocked_use": [
        "production prediction",
        "synthetic outbreak simulation",
        "individual-level tracking",
        "pathogen engineering or optimization",
    ],
    "requirements_before_modeling": [
        "real aggregate observations",
        "documented source provenance",
        "country and date coverage checks",
        "quality flags and missingness review",
        "human approval for model target definitions",
    ],
}


@dataclass(frozen=True)
class ValidationIssue:
    severity: ValidationSeverity
    code: str
    message: str
    field: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ValidationResult:
    ok: bool
    errors: tuple[ValidationIssue, ...] = ()
    warnings: tuple[ValidationIssue, ...] = ()

    def as_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "errors": [issue.as_dict() for issue in self.errors],
            "warnings": [issue.as_dict() for issue in self.warnings],
        }


@dataclass(frozen=True)
class SourceAvailability:
    source_id: str
    country_iso3: str
    status: AvailabilityStatus
    coverage_notes: str
    supported_countries: tuple[str, ...] = ()
    checked_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def as_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["supported_countries"] = list(self.supported_countries)
        return data


@dataclass(frozen=True)
class SourceDescription:
    source_id: str
    name: str
    category: str
    owner: str
    official_url: str
    description: str
    geographic_coverage: str
    supported_countries: tuple[str, ...]
    granularity: str
    temporal_resolution: str
    update_cadence: str
    likely_fields: tuple[str, ...]
    file_formats: tuple[str, ...]
    access_type: str
    license_notes: str
    provenance_notes: str
    data_quality_notes: str
    limitations: str
    adapter_status: str = "placeholder"
    country_availability: str = "unknown"
    last_verified_date: str | None = None
    aggregate_only: bool = True
    privacy_classification: str = "aggregate public"
    safety_notes: tuple[str, ...] = (
        "Aggregate records only.",
        "No individual-level tracking.",
        "No generated production predictions.",
    )
    model_readiness: Mapping[str, Any] = field(default_factory=lambda: dict(MODEL_READINESS_PLACEHOLDER))
    warnings: tuple[str, ...] = ()

    def as_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["supported_countries"] = list(self.supported_countries)
        data["likely_fields"] = list(self.likely_fields)
        data["file_formats"] = list(self.file_formats)
        data["safety_notes"] = list(self.safety_notes)
        data["warnings"] = list(self.warnings)
        data["model_readiness"] = dict(self.model_readiness)
        return data


@dataclass(frozen=True)
class ObservationBatch:
    source_id: str
    country_iso3: str
    start_date: str | None
    end_date: str | None
    records: tuple[Mapping[str, Any], ...] = ()
    status: Literal["empty", "invalid_request"] = "empty"
    warnings: tuple[str, ...] = ()
    limitations: tuple[str, ...] = ()
    fetched_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def as_dict(self) -> dict[str, Any]:
        return {
            "source_id": self.source_id,
            "country_iso3": self.country_iso3,
            "start_date": self.start_date,
            "end_date": self.end_date,
            "records": [dict(record) for record in self.records],
            "status": self.status,
            "warnings": list(self.warnings),
            "limitations": list(self.limitations),
            "fetched_at": self.fetched_at,
        }


class BaseConnector(ABC):
    """Base contract every source adapter must implement."""

    connector_kind: ConnectorKind = "source_metadata"

    @abstractmethod
    def source_id(self) -> str:
        """Return the stable registry source ID."""

    @abstractmethod
    def describe_source(self) -> SourceDescription:
        """Return source-level metadata and safety constraints."""

    @abstractmethod
    def check_availability(self, country_iso3: str) -> SourceAvailability:
        """Return country-level source availability without implying live data."""

    @abstractmethod
    def fetch_metadata(self) -> Mapping[str, Any]:
        """Return source metadata for registry/API responses."""

    @abstractmethod
    def fetch_observations(
        self,
        country_iso3: str,
        start_date: date | datetime | str | None,
        end_date: date | datetime | str | None,
    ) -> ObservationBatch:
        """Fetch real aggregate observations, or an empty batch if not configured."""

    @abstractmethod
    def normalize(self, raw_record: Mapping[str, Any]) -> Mapping[str, Any]:
        """Normalize a raw aggregate record into a backend-safe shape."""

    @abstractmethod
    def validate(self, normalized_record: Mapping[str, Any]) -> ValidationResult:
        """Validate that a normalized record is aggregate-only and provenance-safe."""

    @abstractmethod
    def get_limitations(self) -> tuple[str, ...]:
        """Return source-specific limitations."""


class SourceMetadataConnector(BaseConnector):
    connector_kind: ConnectorKind = "source_metadata"


class TimeSeriesConnector(BaseConnector):
    connector_kind: ConnectorKind = "time_series"


class GeospatialConnector(BaseConnector):
    connector_kind: ConnectorKind = "geospatial"


class NewsConnector(BaseConnector):
    connector_kind: ConnectorKind = "news"


class PlaceholderConnector(BaseConnector):
    """Safe default implementation for metadata-only connector placeholders."""

    metadata: SourceDescription
    connector_kind: ConnectorKind = "source_metadata"
    placeholder_warning = (
        "No live ingestion is configured for this source. Returning metadata and empty observations only."
    )

    def source_id(self) -> str:
        return self.describe_source().source_id

    def describe_source(self) -> SourceDescription:
        return self.metadata

    def check_availability(self, country_iso3: str) -> SourceAvailability:
        iso3 = normalize_iso3(country_iso3)
        metadata = self.describe_source()
        supported = tuple(country.upper() for country in metadata.supported_countries)

        if not iso3:
            return SourceAvailability(
                source_id=metadata.source_id,
                country_iso3="",
                status="unknown",
                supported_countries=supported,
                coverage_notes="Country ISO3 code was not provided.",
            )

        if "GLOBAL" in supported:
            return SourceAvailability(
                source_id=metadata.source_id,
                country_iso3=iso3,
                status="unknown",
                supported_countries=supported,
                coverage_notes="Source metadata is global, but country-specific filtering has not been implemented.",
            )

        if iso3 in supported:
            return SourceAvailability(
                source_id=metadata.source_id,
                country_iso3=iso3,
                status="partial",
                supported_countries=supported,
                coverage_notes="Registry metadata lists this country, but the backend adapter is a placeholder.",
            )

        if metadata.country_availability == "unknown" or not supported:
            status: AvailabilityStatus = "unknown"
            notes = "Country coverage has not been verified for this source."
        else:
            status = "unavailable"
            notes = "Registry metadata does not list this country for this source."

        return SourceAvailability(
            source_id=metadata.source_id,
            country_iso3=iso3,
            status=status,
            supported_countries=supported,
            coverage_notes=notes,
        )

    def fetch_metadata(self) -> Mapping[str, Any]:
        metadata = self.describe_source()
        return {
            "source": metadata.as_dict(),
            "connector_kind": self.connector_kind,
            "limitations": list(self.get_limitations()),
            "observation_policy": "empty_until_real_aggregate_ingestion_is_configured",
        }

    def fetch_observations(
        self,
        country_iso3: str,
        start_date: date | datetime | str | None,
        end_date: date | datetime | str | None,
    ) -> ObservationBatch:
        start, end, date_warnings = normalize_date_window(start_date, end_date)
        status: Literal["empty", "invalid_request"] = "invalid_request" if date_warnings else "empty"
        return ObservationBatch(
            source_id=self.source_id(),
            country_iso3=normalize_iso3(country_iso3),
            start_date=start,
            end_date=end,
            records=(),
            status=status,
            warnings=(self.placeholder_warning, *date_warnings),
            limitations=self.get_limitations(),
        )

    def normalize(self, raw_record: Mapping[str, Any]) -> Mapping[str, Any]:
        if not isinstance(raw_record, Mapping):
            return {
                "source_id": self.source_id(),
                "_normalization_error": "raw_record must be a mapping/object",
            }

        normalized: dict[str, Any] = {"source_id": str(raw_record.get("source_id") or self.source_id())}
        dropped_fields: list[str] = []
        rejected_fields: list[str] = []

        for key, value in raw_record.items():
            normalized_key = normalize_field_name(str(key))
            if normalized_key in SENSITIVE_OR_TRACE_FIELDS:
                rejected_fields.append(str(key))
                continue
            if normalized_key in SAFE_AGGREGATE_FIELDS:
                normalized[normalized_key] = value
            else:
                dropped_fields.append(str(key))

        if "country" in normalized and "country_iso3" not in normalized:
            normalized["country_iso3"] = normalize_iso3(str(normalized["country"]))
        elif "country_iso3" in normalized:
            normalized["country_iso3"] = normalize_iso3(str(normalized["country_iso3"]))

        if rejected_fields:
            normalized["_rejected_fields"] = rejected_fields
        if dropped_fields:
            normalized["_dropped_fields"] = dropped_fields

        return normalized

    def validate(self, normalized_record: Mapping[str, Any]) -> ValidationResult:
        errors: list[ValidationIssue] = []
        warnings: list[ValidationIssue] = []

        if not isinstance(normalized_record, Mapping):
            errors.append(
                ValidationIssue(
                    severity="error",
                    code="not_mapping",
                    message="Normalized record must be a mapping/object.",
                )
            )
            return ValidationResult(ok=False, errors=tuple(errors), warnings=tuple(warnings))

        if normalized_record.get("_normalization_error"):
            errors.append(
                ValidationIssue(
                    severity="error",
                    code="normalization_failed",
                    message=str(normalized_record["_normalization_error"]),
                )
            )

        rejected_fields = normalized_record.get("_rejected_fields") or []
        if rejected_fields:
            errors.append(
                ValidationIssue(
                    severity="error",
                    code="individual_or_trace_level_fields",
                    message=(
                        "Record contains individual-level, device-level, vessel-level, flight-level, "
                        "or exact trace fields that Sentinel Atlas must not expose."
                    ),
                    field=", ".join(str(field) for field in rejected_fields),
                )
            )

        dropped_fields = normalized_record.get("_dropped_fields") or []
        if dropped_fields:
            warnings.append(
                ValidationIssue(
                    severity="warning",
                    code="unsupported_fields_dropped",
                    message="Unsupported fields were dropped during normalization.",
                    field=", ".join(str(field) for field in dropped_fields),
                )
            )

        source_id = normalized_record.get("source_id")
        if source_id and str(source_id) != self.source_id():
            warnings.append(
                ValidationIssue(
                    severity="warning",
                    code="source_id_overridden",
                    message="Record source_id does not match this connector and should be reviewed.",
                    field="source_id",
                )
            )

        if not normalized_record.get("provenance") and not normalized_record.get("source_url"):
            warnings.append(
                ValidationIssue(
                    severity="warning",
                    code="missing_provenance",
                    message="Aggregate records should include provenance or source_url before display.",
                    field="provenance",
                )
            )

        return ValidationResult(ok=not errors, errors=tuple(errors), warnings=tuple(warnings))

    def get_limitations(self) -> tuple[str, ...]:
        metadata = self.describe_source()
        return (
            metadata.limitations,
            "Placeholder connector only; it does not fetch live observations.",
            "Do not use this connector output as a production nowcast, forecast, or risk estimate.",
            "No individual, device, flight, vessel, or patient-level records are accepted.",
        )


class PlaceholderSourceMetadataConnector(PlaceholderConnector, SourceMetadataConnector):
    connector_kind: ConnectorKind = "source_metadata"


class PlaceholderTimeSeriesConnector(PlaceholderConnector, TimeSeriesConnector):
    connector_kind: ConnectorKind = "time_series"


class PlaceholderGeospatialConnector(PlaceholderConnector, GeospatialConnector):
    connector_kind: ConnectorKind = "geospatial"


class PlaceholderNewsConnector(PlaceholderConnector, NewsConnector):
    connector_kind: ConnectorKind = "news"


def normalize_iso3(country_iso3: str | None) -> str:
    return (country_iso3 or "").strip().upper()


def normalize_field_name(field_name: str) -> str:
    return field_name.strip().lower().replace(" ", "_").replace("-", "_")


def normalize_date_window(
    start_date: date | datetime | str | None,
    end_date: date | datetime | str | None,
) -> tuple[str | None, str | None, tuple[str, ...]]:
    warnings: list[str] = []
    start = coerce_date(start_date, "start_date", warnings)
    end = coerce_date(end_date, "end_date", warnings)

    if start and end and start > end:
        warnings.append("start_date must be on or before end_date.")

    return start, end, tuple(warnings)


def coerce_date(value: date | datetime | str | None, field_name: str, warnings: list[str]) -> str | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date().isoformat()
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, str):
        try:
            return date.fromisoformat(value.strip()).isoformat()
        except ValueError:
            warnings.append(f"{field_name} must be an ISO date in YYYY-MM-DD format.")
            return None

    warnings.append(f"{field_name} must be a date, datetime, ISO date string, or null.")
    return None


def source_description(
    *,
    source_id: str,
    name: str,
    category: str,
    owner: str,
    official_url: str,
    description: str,
    geographic_coverage: str,
    supported_countries: Sequence[str],
    granularity: str,
    temporal_resolution: str,
    update_cadence: str,
    likely_fields: Sequence[str],
    file_formats: Sequence[str],
    access_type: str,
    license_notes: str,
    provenance_notes: str,
    data_quality_notes: str,
    limitations: str,
    adapter_status: str = "placeholder",
    country_availability: str = "unknown",
    last_verified_date: str | None = None,
    aggregate_only: bool = True,
    privacy_classification: str = "aggregate public",
    safety_notes: Iterable[str] | None = None,
    model_readiness: Mapping[str, Any] | None = None,
    warnings: Iterable[str] = (),
) -> SourceDescription:
    return SourceDescription(
        source_id=source_id,
        name=name,
        category=category,
        owner=owner,
        official_url=official_url,
        description=description,
        geographic_coverage=geographic_coverage,
        supported_countries=tuple(country.upper() for country in supported_countries),
        granularity=granularity,
        temporal_resolution=temporal_resolution,
        update_cadence=update_cadence,
        likely_fields=tuple(likely_fields),
        file_formats=tuple(file_formats),
        access_type=access_type,
        license_notes=license_notes,
        provenance_notes=provenance_notes,
        data_quality_notes=data_quality_notes,
        limitations=limitations,
        adapter_status=adapter_status,
        country_availability=country_availability,
        last_verified_date=last_verified_date,
        aggregate_only=aggregate_only,
        privacy_classification=privacy_classification,
        safety_notes=tuple(
            safety_notes
            or (
                "Aggregate records only.",
                "No individual-level tracking.",
                "No generated production predictions.",
            )
        ),
        model_readiness=dict(model_readiness or MODEL_READINESS_PLACEHOLDER),
        warnings=tuple(warnings),
    )


class StaticMetadataConnector(PlaceholderSourceMetadataConnector):
    """Compatibility wrapper for earlier metadata-only connector modules.

    New code should prefer explicit connector classes, but this keeps older
    ``create_connector`` modules importable while preserving the no-observation
    placeholder behavior.
    """

    def __init__(
        self,
        *,
        source_id: str,
        name: str,
        category: str,
        publisher: str | None = None,
        official_url: str | None = None,
        access_type: str | None = None,
        license: str | None = None,
        geographic_coverage: str | None = None,
        temporal_resolution: str | None = None,
        update_cadence: str | None = None,
        adapter_status: str = "placeholder",
        reliability_tier: str = "unknown",
        limitations: list[str] | None = None,
        provenance_notes: str | None = None,
        default_coverage_status: str = "unknown",
    ) -> None:
        self.default_coverage_status = _normalize_availability_status(default_coverage_status)
        self.metadata = source_description(
            source_id=source_id,
            name=name,
            category=category,
            owner=publisher or "Unknown",
            official_url=official_url or "",
            description=f"Metadata-only placeholder for {name}.",
            geographic_coverage=geographic_coverage or "Unknown",
            supported_countries=(),
            granularity="Unknown",
            temporal_resolution=temporal_resolution or "Unknown",
            update_cadence=update_cadence or "Unknown",
            likely_fields=(),
            file_formats=(),
            access_type=access_type or "unknown",
            license_notes=license or "Unknown; verify before ingestion.",
            provenance_notes=provenance_notes or "No live ingestion configured.",
            data_quality_notes=f"Reliability tier: {reliability_tier}. Requires source-specific QA.",
            limitations=" ".join(limitations or ("Placeholder connector does not fetch live data.",)),
            adapter_status=adapter_status,
            country_availability=self.default_coverage_status,
            warnings=("Compatibility connector; prefer the registry connector classes for new routes.",),
        )

    def check_availability(self, country_iso3: str) -> SourceAvailability:
        availability = super().check_availability(country_iso3)
        return SourceAvailability(
            source_id=availability.source_id,
            country_iso3=availability.country_iso3,
            status=self.default_coverage_status,
            supported_countries=availability.supported_countries,
            coverage_notes=availability.coverage_notes,
        )


def _normalize_availability_status(status: str) -> AvailabilityStatus:
    if status == "unavailable":
        return "unavailable"
    if status in {"available", "partial"}:
        return "partial"
    return "unknown"
