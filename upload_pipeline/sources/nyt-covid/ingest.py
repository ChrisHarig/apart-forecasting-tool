"""NYT COVID-19 — US county/state daily series.

Pulls the New York Times COVID-19 county-level series. The repo also has a
`us-states.csv` and `us.csv`; we ingest counties (the most granular and
largest) and synthesise state + national rolls on the fly is left to the
dashboard. The county feed is cumulative (`cases`, `deaths` are running
totals) — schema-correctly we mark them `value_type: cumulative`.

Source: https://github.com/nytimes/covid-19-data
File:   us-counties.csv
Cadence: daily
Geography: US counties (FIPS 5-digit)
History: 2020-01-21 — present (archived 2023-03)
"""
from __future__ import annotations

from io import StringIO
from pathlib import Path

import pandas as pd
import requests

CSV_URL = (
    "https://raw.githubusercontent.com/nytimes/covid-19-data/master/us-counties.csv"
)


def fetch() -> pd.DataFrame:
    print(f"Downloading {CSV_URL}")
    resp = requests.get(CSV_URL, timeout=180)
    resp.raise_for_status()
    return pd.read_csv(StringIO(resp.text))


def parse_normalize(raw: pd.DataFrame) -> pd.DataFrame:
    df = raw.copy()
    df["date"] = pd.to_datetime(df["date"], utc=True, errors="raise")

    # NYT uses string FIPS in the `fips` column; missing for "Unknown" rows.
    df = df.dropna(subset=["fips"]).copy()
    df["location_id"] = df["fips"].astype(int).astype(str).str.zfill(5)
    df["location_level"] = pd.Categorical(
        ["subnational-county"] * len(df), categories=["subnational-county"]
    )
    df["location_name"] = df["county"].astype(str) + ", " + df["state"].astype(str)

    df["cases"] = pd.to_numeric(df["cases"], errors="coerce")
    df["deaths"] = pd.to_numeric(df["deaths"], errors="coerce")

    keep = ["date", "location_id", "location_level", "location_name", "cases", "deaths"]
    df = df[keep]
    df = df.sort_values(["date", "location_id"]).reset_index(drop=True)
    return df


def main() -> None:
    raw = fetch()
    print(f"Raw rows: {len(raw):,}")
    df = parse_normalize(raw)
    print(f"After normalization: {len(df):,} rows × {len(df.columns)} cols")
    print(f"  date range: {df['date'].min().date()} → {df['date'].max().date()}")
    print(f"  unique counties: {df['location_id'].nunique()}")

    out_dir = Path(__file__).parent / "data"
    out_dir.mkdir(exist_ok=True)
    out_path = out_dir / "nyt-covid.parquet"
    df.to_parquet(out_path, index=False)
    print(f"Wrote {out_path} ({out_path.stat().st_size / 1024 / 1024:.2f} MB)")


if __name__ == "__main__":
    main()
