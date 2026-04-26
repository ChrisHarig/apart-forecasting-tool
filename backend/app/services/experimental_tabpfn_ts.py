from __future__ import annotations

from datetime import date
import importlib
import importlib.util
import os
from typing import Any

import pandas as pd


MODEL_ID = "experimental_tabpfn_ts"
TABPFN_DISABLE_TELEMETRY_ENV = "TABPFN_DISABLE_TELEMETRY"
TABPFN_MODULE_CANDIDATES = ("tabpfn_time_series",)
MIN_TRAIN_POINTS = 16
FREQUENCY_TO_PANDAS = {"daily": "D", "weekly": "W", "monthly": "MS"}


class TabPFNTimeSeriesUnavailable(RuntimeError):
    """Raised when the optional TabPFN-Time-Series dependency is not usable locally."""


class TabPFNTimeSeriesError(RuntimeError):
    """Raised when the experimental TabPFN-Time-Series forecast path fails."""


def is_tabpfn_ts_available() -> bool:
    return any(importlib.util.find_spec(name) is not None for name in TABPFN_MODULE_CANDIDATES)


def get_tabpfn_dependency_status() -> str:
    return "available" if is_tabpfn_ts_available() else "missing_optional_dependency"


def forecast_with_tabpfn_ts(
    train_observations: list[tuple[date, float]],
    target_dates: list[date],
    frequency: str,
) -> tuple[list[float], list[dict[str, str]]]:
    """Run the optional local TabPFN-Time-Series path against fixed challenge dates.

    This wrapper intentionally does not fall back to another model. If the optional
    package is missing or does not expose a supported local API, callers receive a
    structured unavailable/failed status rather than fabricated predictions.
    """

    os.environ.setdefault(TABPFN_DISABLE_TELEMETRY_ENV, "1")

    if len(train_observations) < MIN_TRAIN_POINTS:
        raise TabPFNTimeSeriesError(f"Need at least {MIN_TRAIN_POINTS} training observations for {MODEL_ID}.")
    if not target_dates:
        raise TabPFNTimeSeriesError("Target dates are required for TabPFN-Time-Series forecasting.")
    if frequency not in FREQUENCY_TO_PANDAS:
        raise TabPFNTimeSeriesError("TabPFN-Time-Series supports daily, weekly, or monthly challenge frequencies.")

    module = _import_tabpfn_module()
    pipeline_class = _get_attribute(module, "TabPFNTSPipeline")
    mode_class = _get_attribute(module, "TabPFNMode")
    if pipeline_class is None:
        raise TabPFNTimeSeriesUnavailable(
            "Installed tabpfn-time-series package does not expose TabPFNTSPipeline for local forecasting."
        )

    frame = pd.DataFrame(
        {
            "unique_id": [MODEL_ID] * len(train_observations),
            "ds": pd.to_datetime([day for day, _value in train_observations]),
            "y": [float(value) for _day, value in train_observations],
        }
    )
    pipeline = _build_local_pipeline(pipeline_class, mode_class)
    raw_forecast = _call_forecast(pipeline, frame, len(target_dates), frequency)
    values = _extract_prediction_values(raw_forecast, len(target_dates))
    warnings = [
        {
            "code": "experimental_model",
            "message": "Experimental TabPFN-Time-Series ran as a backend-owned benchmark only.",
            "severity": "warning",
        },
        {
            "code": "prediction_intervals_unavailable",
            "message": "TabPFN-Time-Series prediction intervals are not exposed by this experimental wrapper.",
            "severity": "info",
        },
    ]
    return values, warnings


def _import_tabpfn_module() -> Any:
    for module_name in TABPFN_MODULE_CANDIDATES:
        if importlib.util.find_spec(module_name) is not None:
            return importlib.import_module(module_name)
    raise TabPFNTimeSeriesUnavailable(
        "Optional dependency tabpfn-time-series is not installed. Install backend with `pip install -e \".[dev,experimental]\"`."
    )


def _get_attribute(module: Any, name: str) -> Any | None:
    if hasattr(module, name):
        return getattr(module, name)
    for child_name in ("pipeline", "forecasting", "models"):
        try:
            child = importlib.import_module(f"{module.__name__}.{child_name}")
        except Exception:
            continue
        if hasattr(child, name):
            return getattr(child, name)
    return None


def _build_local_pipeline(pipeline_class: Any, mode_class: Any | None) -> Any:
    if mode_class is not None:
        for mode_name in ("LOCAL", "local"):
            if hasattr(mode_class, mode_name):
                try:
                    return pipeline_class(tabpfn_mode=getattr(mode_class, mode_name))
                except TypeError:
                    break

    for kwargs in ({"tabpfn_mode": "local"}, {"mode": "local"}, {}):
        try:
            return pipeline_class(**kwargs)
        except TypeError:
            continue
    raise TabPFNTimeSeriesUnavailable("TabPFN-Time-Series pipeline could not be initialized in local mode.")


def _call_forecast(pipeline: Any, frame: pd.DataFrame, horizon: int, frequency: str) -> Any:
    freq = FREQUENCY_TO_PANDAS[frequency]
    method_names = ("forecast", "predict")
    call_shapes = (
        {"df": frame, "h": horizon, "freq": freq},
        {"df": frame, "forecast_horizon": horizon, "freq": freq},
        {"data": frame, "h": horizon, "freq": freq},
        {"data": frame, "forecast_horizon": horizon, "freq": freq},
    )
    for method_name in method_names:
        method = getattr(pipeline, method_name, None)
        if method is None:
            continue
        for kwargs in call_shapes:
            try:
                return method(**kwargs)
            except TypeError:
                continue
    raise TabPFNTimeSeriesUnavailable("TabPFN-Time-Series pipeline does not expose a supported local forecast method.")


def _extract_prediction_values(raw_forecast: Any, horizon: int) -> list[float]:
    if isinstance(raw_forecast, pd.DataFrame):
        candidate_columns = [
            column
            for column in raw_forecast.columns
            if column not in {"unique_id", "ds", "date", "target_date"} and pd.api.types.is_numeric_dtype(raw_forecast[column])
        ]
        if not candidate_columns:
            raise TabPFNTimeSeriesError("TabPFN-Time-Series forecast did not include numeric prediction values.")
        values = raw_forecast[candidate_columns[0]].tail(horizon).astype(float).tolist()
    elif isinstance(raw_forecast, dict):
        for key in ("mean", "prediction", "predictions", "yhat"):
            if key in raw_forecast:
                values = [float(value) for value in list(raw_forecast[key])[-horizon:]]
                break
        else:
            raise TabPFNTimeSeriesError("TabPFN-Time-Series forecast dictionary did not include predictions.")
    else:
        try:
            values = [float(value) for value in list(raw_forecast)[-horizon:]]
        except TypeError as exc:
            raise TabPFNTimeSeriesError("TabPFN-Time-Series forecast output is not an iterable prediction series.") from exc

    if len(values) != horizon:
        raise TabPFNTimeSeriesError("TabPFN-Time-Series forecast did not return exactly the challenge horizon.")
    return values
