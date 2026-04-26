"""FluSight Forecast Hub — flu hosp admission target.

The full hub holds (1) target-data (truth) and (2) model-output (forecasts).
For v0.1 we ingest the **target** truth file only — `target-hospital-admissions.csv`
— treating this dataset as the official truth series the hub scores against.
A separate `flusight-forecast-hub-models` source can ingest model-output later.

Source: https://github.com/cdcepi/FluSight-forecast-hub
File:   target-data/target-hospital-admissions.csv
Cadence: weekly
Geography: US states + national
History: 2022-W43 onward
"""
from __future__ import annotations

from io import StringIO
from pathlib import Path

import pandas as pd
import requests

CSV_URL = (
    "https://raw.githubusercontent.com/cdcepi/FluSight-forecast-hub/main/"
    "target-data/target-hospital-admissions.csv"
)


def fetch() -> pd.DataFrame:
    print(f"Downloading {CSV_URL}")
    resp = requests.get(CSV_URL, timeout=180)
    resp.raise_for_status()
    return pd.read_csv(StringIO(resp.text), dtype={"location": str})


def parse_normalize(raw: pd.DataFrame) -> pd.DataFrame:
    df = raw.copy()
    df["date"] = pd.to_datetime(df["date"], utc=True, errors="raise")

    # FluSight uses "US" for national + 2-digit FIPS for states.
    df["location_id"] = df["location"]
    df["location_level"] = df["location"].apply(
        lambda x: "national" if x == "US" else "subnational-state"
    )
    df["location_level"] = df["location_level"].astype("category")
    df = df.rename(columns={"location_name": "location_name"})

    df["value"] = pd.to_numeric(df["value"], errors="coerce")
    df["weekly_rate"] = pd.to_numeric(df["weekly_rate"], errors="coerce")

    keep = ["date", "location_id", "location_level", "location_name", "value", "weekly_rate"]
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
    out_path = out_dir / "flusight-forecast-hub.parquet"
    df.to_parquet(out_path, index=False)
    print(f"Wrote {out_path} ({out_path.stat().st_size / 1024:.1f} KB)")


if __name__ == "__main__":
    main()
