"""CDC NWSS — public SARS-CoV-2 wastewater metrics (Socrata).

Pulls the public NWSS dataset. Each row is a sampling event at one wastewater
treatment plant; the public file is biweekly-rolled (`date_start`/`date_end`)
with the percentile of the SARS-CoV-2 viral concentration vs. site history.

The site-level location convention in the schema is `facility:<id>`. We use
`facility:nwss-<wwtp_id>` so the prefix is unambiguous if other facility
sources show up later.

Source: https://data.cdc.gov/resource/2ew6-ywp6.json
Cadence: weekly (rolled biweekly window)
Geography: ~1500+ sampling sites across US states
History: 2020-09 onward
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd
import requests

ENDPOINT = "https://data.cdc.gov/resource/2ew6-ywp6.json"
PAGE_SIZE = 50000


def fetch() -> list[dict]:
    rows: list[dict] = []
    offset = 0
    while True:
        params = {"$limit": PAGE_SIZE, "$offset": offset}
        resp = requests.get(ENDPOINT, params=params, timeout=180)
        resp.raise_for_status()
        page = resp.json()
        if not page:
            break
        rows.extend(page)
        offset += PAGE_SIZE
        print(f"  fetched offset={offset:,}, page={len(page):,}, total={len(rows):,}")
        if len(page) < PAGE_SIZE:
            break
    return rows


def parse_normalize(raw: list[dict]) -> pd.DataFrame:
    df = pd.DataFrame(raw)

    # Use date_end as the canonical date (period-end of the rolled window).
    df["date"] = pd.to_datetime(df["date_end"], utc=True, errors="coerce")
    df = df.dropna(subset=["date"]).copy()

    # Facility-level location ID.
    df["location_id"] = "facility:nwss-" + df["wwtp_id"].astype(str)
    df["location_level"] = pd.Categorical(
        ["facility"] * len(df), categories=["facility"]
    )
    df["location_id_native"] = df["wwtp_id"].astype(str)
    df["location_name"] = df["wwtp_jurisdiction"].astype(str)

    for col in ("ptc_15d", "detect_prop_15d", "percentile", "population_served"):
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    # ptc_15d uses -99 as a sentinel for "insufficient data". Coerce to NaN.
    if "ptc_15d" in df.columns:
        df.loc[df["ptc_15d"] == -99, "ptc_15d"] = pd.NA

    keep = [
        "date", "location_id", "location_level", "location_id_native", "location_name",
        "ptc_15d", "detect_prop_15d", "percentile", "population_served",
        "key_plot_id", "county_fips",
    ]
    df = df[[c for c in keep if c in df.columns]].copy()
    df = df.sort_values(["date", "location_id"]).reset_index(drop=True)
    return df


def main() -> None:
    raw = fetch()
    print(f"\nTotal raw rows: {len(raw):,}")
    df = parse_normalize(raw)
    print(f"After normalization: {len(df):,} rows × {len(df.columns)} cols")
    print(f"  date range: {df['date'].min().date()} → {df['date'].max().date()}")
    print(f"  unique sites: {df['location_id'].nunique()}")

    out_dir = Path(__file__).parent / "data"
    out_dir.mkdir(exist_ok=True)
    out_path = out_dir / "cdc-nwss-wastewater.parquet"
    df.to_parquet(out_path, index=False)
    print(f"Wrote {out_path} ({out_path.stat().st_size / 1024 / 1024:.2f} MB)")


if __name__ == "__main__":
    main()
