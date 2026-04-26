"""UKHSA Dashboard — England COVID-19 daily metrics.

Sibling to `ukhsa-respiratory` (which is weekly + multi-pathogen). This source
holds the daily-cadence COVID-only metrics that don't share units with the
flu/RSV weekly per-100k rates: cases, admissions, occupied beds, ONS deaths.

Pivot is wide-by-metric on a single condition (sars-cov-2) — each metric
column has a coherent unit/value_type. No `condition` row dimension because
this dataset is single-pathogen.

Source: https://api.ukhsa-dashboard.data.gov.uk/api/swagger/
Cadence: daily
Geography: England (national)
History: 2020+
"""
from __future__ import annotations

import time as _time
from pathlib import Path

import pandas as pd
import requests

API_BASE = (
    "https://api.ukhsa-dashboard.data.gov.uk/themes/infectious_disease/"
    "sub_themes/respiratory/topics/COVID-19/geography_types/Nation/"
    "geographies/England/metrics"
)

# UKHSA source metric → abstract metric column.
METRIC_MAP: dict[str, str] = {
    "COVID-19_cases_casesByDay":              "cases",
    "COVID-19_healthcare_admissionByDay":     "admissions",
    "COVID-19_healthcare_occupiedBedsByDay":  "occupied_beds",
    "COVID-19_deaths_ONSByDay":               "deaths_ons",
    "COVID-19_testing_PCRcountByDay":         "pcr_tests",
}
ABSTRACT_METRIC_COLS = sorted(METRIC_MAP.values())


def fetch_metric(metric: str) -> list[dict]:
    url = f"{API_BASE}/{metric}"
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


def parse_normalize(per_metric: dict[str, list[dict]]) -> pd.DataFrame:
    long_rows: list[dict] = []
    for metric, records in per_metric.items():
        abstract = METRIC_MAP[metric]
        for r in records:
            long_rows.append({
                "date": r["date"],
                "abstract_metric": abstract,
                "value": r["metric_value"],
            })
    long_df = pd.DataFrame(long_rows)
    if long_df.empty:
        return long_df

    long_df["date"] = pd.to_datetime(long_df["date"], utc=True, errors="raise")
    long_df["value"] = pd.to_numeric(long_df["value"], errors="coerce")

    wide = long_df.pivot_table(
        index=["date"], columns="abstract_metric",
        values="value", aggfunc="first",
    ).reset_index()
    wide.columns.name = None
    for col in ABSTRACT_METRIC_COLS:
        if col not in wide.columns:
            wide[col] = pd.NA

    wide["location_id"] = "GB-ENG"
    wide["location_level"] = pd.Categorical(
        ["subnational-state"] * len(wide), categories=["subnational-state"]
    )
    wide["location_name"] = "England"

    keep = ["date", "location_id", "location_level", "location_name", *ABSTRACT_METRIC_COLS]
    wide = wide[keep].copy()
    wide = wide.sort_values("date").reset_index(drop=True)
    return wide


def main() -> None:
    per_metric: dict[str, list[dict]] = {}
    for metric in METRIC_MAP:
        print(f"Fetching {metric}")
        rows = fetch_metric(metric)
        print(f"  {len(rows):,}")
        per_metric[metric] = rows

    df = parse_normalize(per_metric)
    print(f"\nNormalized: {len(df):,} rows × {len(df.columns)} cols")
    if not df.empty:
        print(f"  date range: {df['date'].min().date()} → {df['date'].max().date()}")
        for col in ABSTRACT_METRIC_COLS:
            n_pop = int(df[col].notna().sum())
            print(f"    {col}: {n_pop:,} populated ({100 * n_pop / len(df):.1f}%)")

    out_dir = Path(__file__).parent / "data"
    out_dir.mkdir(exist_ok=True)
    out_path = out_dir / "ukhsa-covid-daily.parquet"
    df.to_parquet(out_path, index=False)
    print(f"Wrote {out_path}")


if __name__ == "__main__":
    main()
