"""Flu MetroCast Hub — sub-state flu hospitalisation forecasts (truth file).

Pulls the truth file (`time-series.csv`) from reichlab/flu-metrocast. Each row
is a city/county weekly hosp admission count, modelled by participating teams.

Source: https://github.com/reichlab/flu-metrocast
File:   target-data/time-series.csv
Cadence: weekly
Geography: ~30 US sub-state metro areas (cities / counties)
History: 2024+
"""
from __future__ import annotations

from io import StringIO
from pathlib import Path

import pandas as pd
import requests

CSV_URL = (
    "https://raw.githubusercontent.com/reichlab/flu-metrocast/main/"
    "target-data/time-series.csv"
)


def fetch() -> pd.DataFrame:
    print(f"Downloading {CSV_URL}")
    resp = requests.get(CSV_URL, timeout=180)
    resp.raise_for_status()
    return pd.read_csv(StringIO(resp.text), dtype={"location": str})


def parse_normalize(raw: pd.DataFrame) -> pd.DataFrame:
    df = raw.copy()
    date_col = "target_end_date" if "target_end_date" in df.columns else "date"
    df["date"] = pd.to_datetime(df[date_col], utc=True, errors="raise")
    df["location_id"] = df["location"].astype(str)
    # MetroCast uses non-FIPS sub-state IDs (e.g. NYC, LA). Mark as subnational-city
    # with synthetic prefix `US-METRO-<id>` so the schema's location pattern allows them.
    df["location_id"] = "US-METRO-" + df["location_id"].str.upper().str.replace(r"\W", "", regex=True)
    df["location_level"] = pd.Categorical(
        ["subnational-city"] * len(df), categories=["subnational-city"]
    )
    df["location_name"] = df["location"].astype(str)
    val_col = "observation" if "observation" in df.columns else "value"
    df["value"] = pd.to_numeric(df[val_col], errors="coerce")

    keep = ["date", "location_id", "location_level", "location_name", "value"]
    if "target" in df.columns:
        keep.append("target")
    df = df[[c for c in keep if c in df.columns]].copy()
    df = df.sort_values(["date", "location_id"]).reset_index(drop=True)
    return df


def main() -> None:
    raw = fetch()
    print(f"Raw rows: {len(raw):,}, cols: {list(raw.columns)}")
    df = parse_normalize(raw)
    print(f"After normalization: {len(df):,} rows × {len(df.columns)} cols")
    if not df.empty:
        print(f"  date range: {df['date'].min().date()} → {df['date'].max().date()}")
        print(f"  metros: {df['location_id'].nunique()}")

    out_dir = Path(__file__).parent / "data"
    out_dir.mkdir(exist_ok=True)
    out_path = out_dir / "flu-metrocast-hub.parquet"
    df.to_parquet(out_path, index=False)
    print(f"Wrote {out_path}")


if __name__ == "__main__":
    main()
