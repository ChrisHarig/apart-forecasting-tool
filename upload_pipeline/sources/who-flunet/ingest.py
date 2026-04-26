"""WHO FluNet — global weekly influenza virology.

Pulls FluNet's `VIW_FNT` view from WHO's xMart public OData endpoint. Each row
is (country, ISO week) with influenza A/B specimens processed and subtype
breakdowns. Pagination is required (full dataset is ~700k rows).

Source: https://xmart-api-public.who.int/FLUMART/VIW_FNT
Cadence: weekly
Geography: 100+ countries
History: 1995+ (per-country availability varies)
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd
import requests

ENDPOINT = "https://xmart-api-public.who.int/FLUMART/VIW_FNT"
PAGE_SIZE = 50000

VALUE_COLUMNS = [
    "SPEC_PROCESSED_NB",   # specimens processed
    "SPEC_RECEIVED_NB",    # specimens received
    "INF_A",               # all A
    "INF_B",               # all B
    "INF_ALL",             # all flu positive
    "INF_NEGATIVE",        # negative
    "AH1N12009",           # subtype counts
    "AH1", "AH3", "AH5", "AH7N9",
    "BVIC_2DEL", "BVIC_3DEL", "BYAM",
    "RSV",                 # FluNet also reports RSV when labs report it
]


def fetch() -> list[dict]:
    rows: list[dict] = []
    skip = 0
    while True:
        params = {"$format": "json", "$top": PAGE_SIZE, "$skip": skip}
        resp = requests.get(ENDPOINT, params=params, timeout=240)
        resp.raise_for_status()
        page = resp.json().get("value", [])
        if not page:
            break
        rows.extend(page)
        skip += PAGE_SIZE
        print(f"  skip={skip:,}  total={len(rows):,}")
        if len(page) < PAGE_SIZE:
            break
    return rows


def parse_normalize(raw: list[dict]) -> pd.DataFrame:
    df = pd.DataFrame(raw)
    df["date"] = pd.to_datetime(df["ISO_WEEKSTARTDATE"], utc=True, errors="coerce")
    df = df.dropna(subset=["date"]).copy()
    # Period-end (Sunday) by adding 6 days to ISO Monday.
    df["date"] = df["date"] + pd.Timedelta(days=6)

    # WHO `ISO2` already has alpha-2; trust it for `location_id`.
    df["location_id"] = df["ISO2"].astype(str).str.upper()
    df = df[df["location_id"].str.match(r"^[A-Z]{2}$", na=False)].copy()
    df["location_level"] = pd.Categorical(
        ["national"] * len(df), categories=["national"]
    )
    df = df.rename(columns={"COUNTRY_AREA_TERRITORY": "location_name"})

    for col in VALUE_COLUMNS:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    keep = ["date", "location_id", "location_level", "location_name"]
    keep.extend(c for c in VALUE_COLUMNS if c in df.columns)
    df = df[keep].copy()
    df = df.sort_values(["date", "location_id"]).reset_index(drop=True)
    return df


def main() -> None:
    print(f"Fetching {ENDPOINT}")
    raw = fetch()
    print(f"\nTotal raw rows: {len(raw):,}")
    df = parse_normalize(raw)
    print(f"After normalization: {len(df):,} rows × {len(df.columns)} cols")
    print(f"  date range: {df['date'].min().date()} → {df['date'].max().date()}")
    print(f"  countries: {df['location_id'].nunique()}")

    out_dir = Path(__file__).parent / "data"
    out_dir.mkdir(exist_ok=True)
    out_path = out_dir / "who-flunet.parquet"
    df.to_parquet(out_path, index=False)
    print(f"Wrote {out_path} ({out_path.stat().st_size / 1024 / 1024:.2f} MB)")


if __name__ == "__main__":
    main()
