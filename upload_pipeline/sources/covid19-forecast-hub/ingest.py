"""COVID-19 Forecast Hub — COVID hospital admissions target.

Same shape as the FluSight hub. The COVID hub publishes
`target-data/covid-hospital-admissions.csv` as the truth file. Cadence is weekly
period-end Saturday (`target_end_date`).

Source: https://github.com/CDCgov/covid19-forecast-hub
"""
from __future__ import annotations

from io import StringIO
from pathlib import Path

import pandas as pd
import requests

CSV_URL = (
    "https://raw.githubusercontent.com/CDCgov/covid19-forecast-hub/main/"
    "target-data/covid-hospital-admissions.csv"
)


def fetch() -> pd.DataFrame:
    print(f"Downloading {CSV_URL}")
    resp = requests.get(CSV_URL, timeout=180)
    resp.raise_for_status()
    return pd.read_csv(StringIO(resp.text), dtype={"location": str})


def parse_normalize(raw: pd.DataFrame) -> pd.DataFrame:
    df = raw.copy()
    df["date"] = pd.to_datetime(df["target_end_date"], utc=True, errors="raise")
    df["location_id"] = df["location"]
    df["location_level"] = df["location"].apply(
        lambda x: "national" if x == "US" else "subnational-state"
    ).astype("category")
    df = df.rename(columns={"state": "location_name"})
    df["value"] = pd.to_numeric(df["value"], errors="coerce")

    keep = ["date", "location_id", "location_level", "location_name", "value"]
    df = df[keep].copy()
    df = df.sort_values(["date", "location_id"]).reset_index(drop=True)
    return df


def main() -> None:
    raw = fetch()
    print(f"Raw rows: {len(raw):,}")
    df = parse_normalize(raw)
    print(f"After normalization: {len(df):,} rows × {len(df.columns)} cols")
    print(f"  date range: {df['date'].min().date()} → {df['date'].max().date()}")

    out_dir = Path(__file__).parent / "data"
    out_dir.mkdir(exist_ok=True)
    out_path = out_dir / "covid19-forecast-hub.parquet"
    df.to_parquet(out_path, index=False)
    print(f"Wrote {out_path}")


if __name__ == "__main__":
    main()
