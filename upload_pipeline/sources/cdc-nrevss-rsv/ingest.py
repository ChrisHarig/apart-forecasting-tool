"""CDC NREVSS RSV — weekly RSV antigen + PCR test counts and positives.

NREVSS publishes the RSV portion as a Socrata dataset at id `52kb-ccu2`.
Each row is (week, HHS region, test type) with `rsvtest` (specimens tested)
and `rsvpos` (positive). One canonical extra column `outlier` flags points
the source itself excluded.

Source: https://data.cdc.gov/resource/52kb-ccu2.json
Cadence: weekly (Saturday period-end)
Geography: 10 HHS regions
History: ~2010 onward (varies by test type)
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd
import requests

ENDPOINT = "https://data.cdc.gov/resource/52kb-ccu2.json"
PAGE_SIZE = 50000


def fetch() -> list[dict]:
    rows: list[dict] = []
    offset = 0
    while True:
        params = {"$limit": PAGE_SIZE, "$offset": offset}
        resp = requests.get(ENDPOINT, params=params, timeout=120)
        resp.raise_for_status()
        page = resp.json()
        if not page:
            break
        rows.extend(page)
        offset += PAGE_SIZE
        if len(page) < PAGE_SIZE:
            break
    return rows


def parse_normalize(raw: list[dict]) -> pd.DataFrame:
    df = pd.DataFrame(raw)

    # `repweekdate` like "10JUL2010" — period-end Saturday.
    df["date"] = pd.to_datetime(df["repweekdate"], format="%d%b%Y", utc=True)

    # HHS region as integer 1-10 → US-HHS-N.
    df["location_id"] = "US-HHS-" + df["hhs_region"].astype(str)
    df["location_level"] = pd.Categorical(
        ["subnational-region"] * len(df), categories=["subnational-region"]
    )
    df["location_name"] = "HHS " + df["hhs_region"].astype(str)

    df["rsvpos"] = pd.to_numeric(df["rsvpos"], errors="coerce")
    df["rsvtest"] = pd.to_numeric(df["rsvtest"], errors="coerce")
    df["outlier"] = pd.to_numeric(df["outlier"], errors="coerce")

    keep = ["date", "location_id", "location_level", "location_name",
            "testtype", "rsvpos", "rsvtest", "outlier"]
    df = df[keep].copy()
    df = df.sort_values(["date", "location_id", "testtype"]).reset_index(drop=True)
    return df


def main() -> None:
    print(f"Fetching {ENDPOINT}")
    raw = fetch()
    print(f"Raw rows: {len(raw):,}")
    df = parse_normalize(raw)
    print(f"After normalization: {len(df):,} rows × {len(df.columns)} cols")
    print(f"  date range: {df['date'].min().date()} → {df['date'].max().date()}")
    print(f"  test types: {sorted(df['testtype'].unique().tolist())}")

    out_dir = Path(__file__).parent / "data"
    out_dir.mkdir(exist_ok=True)
    out_path = out_dir / "cdc-nrevss-rsv.parquet"
    df.to_parquet(out_path, index=False)
    print(f"Wrote {out_path} ({out_path.stat().st_size / 1024:.1f} KB)")


if __name__ == "__main__":
    main()
