"""RSV Forecast Hub — RSV hospital admissions target.

Truth file is published as a parquet (`target-data/time-series.parquet`).

Source: https://github.com/CDCgov/rsv-forecast-hub
"""
from __future__ import annotations

import io
from pathlib import Path

import pandas as pd
import requests

PARQUET_URL = (
    "https://github.com/CDCgov/rsv-forecast-hub/raw/main/target-data/time-series.parquet"
)


def fetch() -> pd.DataFrame:
    print(f"Downloading {PARQUET_URL}")
    resp = requests.get(PARQUET_URL, timeout=180)
    resp.raise_for_status()
    return pd.read_parquet(io.BytesIO(resp.content))


def parse_normalize(raw: pd.DataFrame) -> pd.DataFrame:
    df = raw.copy()
    # Hubverse RSV parquet columns: target_end_date, as_of, location, target, observation.
    df["date"] = pd.to_datetime(df["target_end_date"], utc=True, errors="raise")
    if "as_of" in df.columns:
        df["as_of"] = pd.to_datetime(df["as_of"], utc=True, errors="coerce")
    df["location_id"] = df["location"].astype(str)
    df["location_level"] = df["location_id"].apply(
        lambda x: "national" if x == "US" else "subnational-state"
    ).astype("category")
    df["location_name"] = df["location_id"]  # no name column in source
    df["value"] = pd.to_numeric(df["observation"], errors="coerce")

    keep = ["date", "as_of", "location_id", "location_level", "location_name", "value"]
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
    print(f"  date range: {df['date'].min().date()} → {df['date'].max().date()}")

    out_dir = Path(__file__).parent / "data"
    out_dir.mkdir(exist_ok=True)
    out_path = out_dir / "rsv-forecast-hub.parquet"
    df.to_parquet(out_path, index=False)
    print(f"Wrote {out_path}")


if __name__ == "__main__":
    main()
