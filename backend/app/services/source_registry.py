"""Source registry service for Sentinel Atlas backend routes.

This module is framework-light on purpose: FastAPI routers can import
``get_source_registry`` as a dependency, while tests and scripts can use the
same registry without starting an ASGI app.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Iterable, Mapping

from app.connectors import BaseConnector, default_connectors


class SourceRegistry:
    """In-memory registry for metadata-only connector placeholders."""

    def __init__(self, connectors: Iterable[BaseConnector] | None = None) -> None:
        self._connectors: dict[str, BaseConnector] = {}
        for connector in connectors or default_connectors():
            source_id = connector.source_id()
            if source_id in self._connectors:
                raise ValueError(f"Duplicate connector source_id: {source_id}")
            self._connectors[source_id] = connector

    def registered_source_ids(self) -> tuple[str, ...]:
        return tuple(self._connectors)

    def list_connectors(self) -> tuple[BaseConnector, ...]:
        return tuple(self._connectors.values())

    def list_source_metadata(self) -> list[dict[str, object]]:
        """Return flattened source metadata for FastAPI source catalog routes."""

        return [_flatten_connector_metadata(connector) for connector in self._connectors.values()]

    def get_connector(self, source_id: str) -> BaseConnector:
        try:
            return self._connectors[source_id]
        except KeyError as exc:
            raise KeyError(f"Unknown source_id: {source_id}") from exc

    def get(self, source_id: str) -> BaseConnector | None:
        return self._connectors.get(source_id)

    def list_sources(self) -> list[Mapping[str, object]]:
        return [connector.fetch_metadata() for connector in self._connectors.values()]

    def describe_source(self, source_id: str) -> Mapping[str, object]:
        return self.get_connector(source_id).fetch_metadata()

    def get_limitations(self, source_id: str) -> tuple[str, ...]:
        return self.get_connector(source_id).get_limitations()

    def check_availability(self, source_id: str, country_iso3: str) -> Mapping[str, object]:
        return self.get_connector(source_id).check_availability(country_iso3).as_dict()

    def check_country_sources(self, country_iso3: str) -> list[Mapping[str, object]]:
        return [
            {
                "source_id": connector.source_id(),
                "connector_kind": connector.connector_kind,
                "availability": connector.check_availability(country_iso3).as_dict(),
                "source": connector.describe_source().as_dict(),
            }
            for connector in self._connectors.values()
        ]

    def fetch_metadata(self, source_id: str) -> Mapping[str, object]:
        return self.get_connector(source_id).fetch_metadata()

    def fetch_observations(
        self,
        source_id: str,
        country_iso3: str,
        start_date: date | datetime | str | None = None,
        end_date: date | datetime | str | None = None,
    ) -> Mapping[str, object]:
        return self.get_connector(source_id).fetch_observations(country_iso3, start_date, end_date).as_dict()

    def normalize_record(self, source_id: str, raw_record: Mapping[str, object]) -> Mapping[str, object]:
        return self.get_connector(source_id).normalize(raw_record)

    def validate_record(self, source_id: str, normalized_record: Mapping[str, object]) -> Mapping[str, object]:
        return self.get_connector(source_id).validate(normalized_record).as_dict()


source_registry = SourceRegistry()


def get_source_registry() -> SourceRegistry:
    """FastAPI dependency hook for future routers."""

    return source_registry


def _flatten_connector_metadata(connector: BaseConnector) -> dict[str, object]:
    description = connector.describe_source()
    metadata = description.as_dict()
    limitations = connector.get_limitations()
    return {
        "id": metadata["source_id"],
        "name": metadata["name"],
        "category": metadata["category"],
        "publisher": metadata["owner"],
        "official_url": metadata["official_url"],
        "access_type": metadata["access_type"],
        "license": metadata["license_notes"],
        "geographic_coverage": metadata["geographic_coverage"],
        "temporal_resolution": metadata["temporal_resolution"],
        "update_cadence": metadata["update_cadence"],
        "adapter_status": metadata["adapter_status"],
        "reliability_tier": metadata.get("model_readiness", {}).get("status", "unknown"),
        "limitations": list(limitations),
        "provenance_notes": metadata["provenance_notes"],
        "supported_countries": metadata["supported_countries"],
        "granularity": metadata["granularity"],
        "likely_fields": metadata["likely_fields"],
        "file_formats": metadata["file_formats"],
        "privacy_classification": metadata["privacy_classification"],
        "aggregate_only": metadata["aggregate_only"],
        "warnings": metadata["warnings"],
        "observation_policy": "empty_until_real_aggregate_ingestion_is_configured",
    }
