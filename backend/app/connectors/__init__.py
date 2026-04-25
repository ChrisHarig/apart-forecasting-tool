"""Sentinel Atlas backend connector exports."""

from __future__ import annotations

from .base import (
    BaseConnector,
    GeospatialConnector,
    NewsConnector,
    ObservationBatch,
    SourceAvailability,
    SourceDescription,
    SourceMetadataConnector,
    TimeSeriesConnector,
    ValidationIssue,
    ValidationResult,
)
from .infrastructure import (
    IMFPortWatchConnector,
    MARADPortsConnector,
    NGAWorldPortIndexConnector,
    NOAAAISConnector,
    OpenSkyConnector,
    OurAirportsConnector,
    USACENavigationConnector,
    UserUploadConnector,
)
from .news import FutureNewsConnector
from .public_health import (
    CDCFluSightCurrentConnector,
    CDCFluSightForecastHubConnector,
    CDCNWSSConnector,
    ReichLabFluSightConnector,
    WastewaterSCANConnector,
    WHOFluNetConnector,
)

__all__ = [
    "BaseConnector",
    "CDCFluSightCurrentConnector",
    "CDCFluSightForecastHubConnector",
    "CDCNWSSConnector",
    "FutureNewsConnector",
    "GeospatialConnector",
    "IMFPortWatchConnector",
    "MARADPortsConnector",
    "NGAWorldPortIndexConnector",
    "NOAAAISConnector",
    "NewsConnector",
    "ObservationBatch",
    "OpenSkyConnector",
    "OurAirportsConnector",
    "ReichLabFluSightConnector",
    "SourceAvailability",
    "SourceDescription",
    "SourceMetadataConnector",
    "TimeSeriesConnector",
    "USACENavigationConnector",
    "UserUploadConnector",
    "ValidationIssue",
    "ValidationResult",
    "WastewaterSCANConnector",
    "WHOFluNetConnector",
    "default_connectors",
]


def default_connectors() -> tuple[BaseConnector, ...]:
    """Return all built-in metadata-only connector placeholders."""

    return (
        WastewaterSCANConnector(),
        CDCNWSSConnector(),
        WHOFluNetConnector(),
        CDCFluSightCurrentConnector(),
        CDCFluSightForecastHubConnector(),
        ReichLabFluSightConnector(),
        OpenSkyConnector(),
        OurAirportsConnector(),
        IMFPortWatchConnector(),
        NGAWorldPortIndexConnector(),
        USACENavigationConnector(),
        NOAAAISConnector(),
        MARADPortsConnector(),
        UserUploadConnector(),
        FutureNewsConnector(),
    )
