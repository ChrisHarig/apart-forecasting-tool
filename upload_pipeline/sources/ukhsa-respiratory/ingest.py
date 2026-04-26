"""UKHSA Dashboard — England weekly respiratory virology + admissions (REST API).

Pulls weekly Influenza, COVID-19, and RSV metrics from the UKHSA dashboard
REST API and emits one row per (date, location, condition) with the
*comparable* metrics as named columns.

Schema fit: this is the long-format-by-condition + wide-by-metric pattern.
Each value column has a single unit/value_type. Where a metric isn't
published for a given pathogen, the cell is NaN — same shape as NHSN HRD's
RSV admissions before mandatory reporting started in 2024-W46.

COVID's daily-cadence metrics (admissions/day, cases/day, occupied beds/day)
do not share units with flu/RSV's weekly per-100k rates; those belong in a
separate `ukhsa-covid-daily` source if we want them later. COVID's
`positivity7DayRolling` is daily but unit-comparable to the weekly positivity
metrics, so we resample it to Saturday week-end before merging.

Source: https://api.ukhsa-dashboard.data.gov.uk/api/swagger/
Cadence: weekly
Geography: England (national)
History: ~2015-06+ for flu ILI; 2020+ for COVID; 2018+ for RSV.
"""
from __future__ import annotations

import time as _time
from pathlib import Path

import pandas as pd
import requests

API_BASE = (
    "https://api.ukhsa-dashboard.data.gov.uk/themes/infectious_disease/"
    "sub_themes/respiratory"
)

# UKHSA source metric → (condition slug, condition_type, abstract metric column).
# We keep only metrics that fit a coherent unit / value_type story. COVID
# daily-only metrics (admissions, cases, ONS deaths, occupied beds) are
# deliberately excluded — they belong in a sibling daily-cadence dataset.
METRIC_MAP: dict[str, tuple[str, str, str]] = {
    # Influenza — 5 weekly metrics
    "influenza_testing_positivityByWeek":               ("influenza",  "pathogen", "positivity"),
    "influenza_healthcare_hospitalAdmissionRateByWeek": ("influenza",  "pathogen", "admission_rate"),
    "influenza_healthcare_ICUHDUadmissionRateByWeek":   ("influenza",  "pathogen", "icu_admission_rate"),
    "influenza_cases_surveyILIRateByWeek":              ("influenza",  "pathogen", "ili_survey_rate"),
    "influenza_cases_surveyParticipantsByWeek":         ("influenza",  "pathogen", "survey_participants"),
    # RSV — 2 weekly metrics
    "RSV_testing_positivityByWeek":                     ("rsv",        "pathogen", "positivity"),
    "RSV_healthcare_admissionRateByWeek":               ("rsv",        "pathogen", "admission_rate"),
    # COVID-19 — only the unit-comparable ones (positivity, resampled to weekly)
    "COVID-19_testing_positivity7DayRolling":           ("sars-cov-2", "pathogen", "positivity"),
}

# UKHSA topic name (URL path segment) per condition slug — needed because the
# API URLs use Topic-Name, not the slug. Derived from METRIC_MAP keys:
TOPIC_OF_PREFIX = {
    "influenza": "Influenza",
    "RSV":       "RSV",
    "COVID-19":  "COVID-19",
}

ABSTRACT_METRIC_COLS = sorted({m for *_, m in METRIC_MAP.values()})

# COVID's positivity is published daily (7-day rolling). Resample to the
# Saturday-week-end the flu/RSV weekly metrics use, taking the value AT that Saturday.
RESAMPLE_TO_WEEKLY = {"COVID-19_testing_positivity7DayRolling"}


def _topic_for_metric(metric: str) -> str:
    # "influenza_..." → "Influenza"; "RSV_..." → "RSV"; "COVID-19_..." → "COVID-19"
    if metric.startswith("influenza_"):
        return "Influenza"
    if metric.startswith("RSV_"):
        return "RSV"
    if metric.startswith("COVID-19_"):
        return "COVID-19"
    raise ValueError(f"Unknown topic prefix in metric {metric!r}")


def fetch_metric(topic: str, metric: str) -> list[dict]:
    url = (
        f"{API_BASE}/topics/{topic}/geography_types/Nation/"
        f"geographies/England/metrics/{metric}"
    )
    rows: list[dict] = []
    next_url = url
    while next_url:
        resp = requests.get(next_url, params={"page_size": 365}, timeout=120)
        if resp.status_code == 404:
            return []
        resp.raise_for_status()
        payload = resp.json()
        rows.extend(payload.get("results", []))
        next_url = payload.get("next")
        _time.sleep(0.3)
    return rows


def _resample_daily_to_saturday(records: list[dict]) -> list[dict]:
    """Keep only the records whose `date` falls on a Saturday (period-end weekly)."""
    out: list[dict] = []
    for r in records:
        d = pd.to_datetime(r["date"])
        if d.weekday() == 5:  # Saturday
            out.append(r)
    return out


def parse_normalize(per_metric_rows: dict[str, list[dict]]) -> pd.DataFrame:
    long_rows: list[dict] = []
    for metric, records in per_metric_rows.items():
        condition, ctype, abstract = METRIC_MAP[metric]
        if metric in RESAMPLE_TO_WEEKLY:
            records = _resample_daily_to_saturday(records)
        for r in records:
            long_rows.append({
                "date": r["date"],
                "condition": condition,
                "condition_type": ctype,
                "abstract_metric": abstract,
                "value": r["metric_value"],
            })
    long_df = pd.DataFrame(long_rows)
    if long_df.empty:
        return long_df

    long_df["date"] = pd.to_datetime(long_df["date"], utc=True, errors="raise")
    long_df["value"] = pd.to_numeric(long_df["value"], errors="coerce")

    # Pivot wide on abstract_metric, keyed by (date, condition).
    # `condition_type` rides along (it's a function of `condition`).
    wide = long_df.pivot_table(
        index=["date", "condition", "condition_type"],
        columns="abstract_metric",
        values="value",
        aggfunc="first",
    ).reset_index()
    wide.columns.name = None

    # Make sure every expected metric column exists (NaN-filled if absent).
    for col in ABSTRACT_METRIC_COLS:
        if col not in wide.columns:
            wide[col] = pd.NA

    wide["location_id"] = "GB-ENG"
    wide["location_level"] = pd.Categorical(
        ["subnational-state"] * len(wide), categories=["subnational-state"]
    )
    wide["location_name"] = "England"
    # condition_native = the human-readable topic
    wide["condition_native"] = wide["condition"].map({
        "influenza": "Influenza",
        "sars-cov-2": "COVID-19",
        "rsv": "RSV",
    })
    wide["condition_type"] = wide["condition_type"].astype("category")

    keep = [
        "date", "location_id", "location_level", "location_name",
        "condition", "condition_type", "condition_native",
        *ABSTRACT_METRIC_COLS,
    ]
    wide = wide[keep].copy()
    wide = wide.sort_values(["date", "condition"]).reset_index(drop=True)
    return wide


def main() -> None:
    per_metric: dict[str, list[dict]] = {}
    for metric in METRIC_MAP:
        topic = _topic_for_metric(metric)
        print(f"Fetching {topic}/{metric}")
        rows = fetch_metric(topic, metric)
        print(f"  {len(rows):,} rows")
        per_metric[metric] = rows

    df = parse_normalize(per_metric)
    print(f"\nNormalized: {len(df):,} rows × {len(df.columns)} cols")
    if not df.empty:
        print(f"  date range: {df['date'].min().date()} → {df['date'].max().date()}")
        print(f"  conditions: {sorted(df['condition'].unique().tolist())}")
        for col in ABSTRACT_METRIC_COLS:
            n_pop = int(df[col].notna().sum())
            print(f"    {col}: {n_pop:,} populated ({100 * n_pop / len(df):.1f}%)")

    out_dir = Path(__file__).parent / "data"
    out_dir.mkdir(exist_ok=True)
    out_path = out_dir / "ukhsa-respiratory.parquet"
    df.to_parquet(out_path, index=False)
    print(f"Wrote {out_path}")


if __name__ == "__main__":
    main()
