"""CDC NSSP / ESSENCE (aggregate) ingest module.

Pulls weekly % of emergency-department visits matching ILI / COVID-19 / RSV
syndromic case definitions from CDC's Socrata endpoint. Data is naturally
long-format — one row per (week, geography, pathogen) — so it's the first
EPI-Eval source to exercise the row-level `condition` / `condition_type`
columns added in v0.1.

Source: https://data.cdc.gov/resource/vutn-jzwm.json
Cadence: weekly (week_end Saturday)
Geography: national + 50 US jurisdictions (no South Dakota; NSSP coverage gap)
History: 2023-10-07+ on this Socrata view (the underlying NSSP system is older)
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd
import requests

SOCRATA_ENDPOINT = "https://data.cdc.gov/resource/vutn-jzwm.json"
PAGE_SIZE = 50000

# Source's long-form pathogen name → (canonical slug, condition_type).
PATHOGEN_TO_CONDITION: dict[str, tuple[str, str]] = {
    "Influenza": ("influenza", "pathogen"),
    "COVID-19": ("sars-cov-2", "pathogen"),
    "RSV": ("rsv", "pathogen"),
}

# State name → 2-digit FIPS. SD is intentionally absent (not in NSSP).
STATE_NAME_TO_FIPS: dict[str, str] = {
    "Alabama": "01", "Alaska": "02", "Arizona": "04", "Arkansas": "05",
    "California": "06", "Colorado": "08", "Connecticut": "09", "Delaware": "10",
    "District of Columbia": "11", "Florida": "12", "Georgia": "13", "Hawaii": "15",
    "Idaho": "16", "Illinois": "17", "Indiana": "18", "Iowa": "19",
    "Kansas": "20", "Kentucky": "21", "Louisiana": "22", "Maine": "23",
    "Maryland": "24", "Massachusetts": "25", "Michigan": "26", "Minnesota": "27",
    "Mississippi": "28", "Missouri": "29", "Montana": "30", "Nebraska": "31",
    "Nevada": "32", "New Hampshire": "33", "New Jersey": "34", "New Mexico": "35",
    "New York": "36", "North Carolina": "37", "North Dakota": "38", "Ohio": "39",
    "Oklahoma": "40", "Oregon": "41", "Pennsylvania": "42", "Rhode Island": "44",
    "South Carolina": "45", "Tennessee": "47", "Texas": "48", "Utah": "49",
    "Vermont": "50", "Virginia": "51", "Washington": "53", "West Virginia": "54",
    "Wisconsin": "55", "Wyoming": "56",
}


def fetch() -> list[dict]:
    rows: list[dict] = []
    offset = 0
    while True:
        params = {"$limit": PAGE_SIZE, "$offset": offset}
        resp = requests.get(SOCRATA_ENDPOINT, params=params, timeout=120)
        resp.raise_for_status()
        page = resp.json()
        if not page:
            break
        rows.extend(page)
        offset += PAGE_SIZE
        if len(page) < PAGE_SIZE:
            break
    return rows


def _resolve_geography(name: str) -> tuple[str, str]:
    if name == "United States":
        return ("US", "national")
    if name in STATE_NAME_TO_FIPS:
        return (STATE_NAME_TO_FIPS[name], "subnational-state")
    raise ValueError(f"Unmapped geography: {name!r}")


def _resolve_pathogen(name: str) -> tuple[str, str]:
    if name not in PATHOGEN_TO_CONDITION:
        raise ValueError(f"Unmapped pathogen: {name!r}")
    return PATHOGEN_TO_CONDITION[name]


def parse_normalize(raw: list[dict]) -> pd.DataFrame:
    df = pd.DataFrame(raw)

    df = df.rename(columns={"week_end": "date"})
    df["date"] = pd.to_datetime(df["date"], utc=True, errors="raise")

    geo_resolved = df["geography"].map(_resolve_geography)
    df["location_id"] = geo_resolved.map(lambda t: t[0])
    df["location_level"] = geo_resolved.map(lambda t: t[1]).astype("category")
    df = df.rename(columns={"geography": "location_name"})

    pathogen_resolved = df["pathogen"].map(_resolve_pathogen)
    df["condition"] = pathogen_resolved.map(lambda t: t[0])
    df["condition_type"] = pathogen_resolved.map(lambda t: t[1]).astype("category")
    df = df.rename(columns={"pathogen": "condition_native"})

    df["percent_visits"] = pd.to_numeric(df["percent_visits"], errors="coerce")

    keep = ["date", "location_id", "location_level", "location_name",
            "condition", "condition_type", "condition_native", "percent_visits"]
    df = df[keep].copy()

    df = df.sort_values(["date", "location_id", "condition"]).reset_index(drop=True)
    return df


def main() -> None:
    print(f"Fetching {SOCRATA_ENDPOINT} ...")
    raw = fetch()
    print(f"  fetched {len(raw):,} rows")

    df = parse_normalize(raw)
    print(f"After normalization: {len(df):,} rows × {len(df.columns)} columns")
    print(f"  date range: {df['date'].min().date()} → {df['date'].max().date()}")
    print(f"  unique locations: {df['location_id'].nunique()}")
    print(f"  unique conditions: {sorted(df['condition'].unique())}")
    print(f"  level breakdown: {df['location_level'].value_counts().to_dict()}")
    print()
    print("Sample (most recent national, all pathogens):")
    sample = df[df["location_id"] == "US"].sort_values("date").tail(3)
    print(sample[["date", "condition", "percent_visits"]].to_string(index=False))

    out_dir = Path(__file__).parent / "data"
    out_dir.mkdir(exist_ok=True)
    out_path = out_dir / "cdc-nssp.parquet"
    df.to_parquet(out_path, index=False)
    print(f"\nWrote {out_path} ({out_path.stat().st_size / 1024 / 1024:.2f} MB)")


if __name__ == "__main__":
    main()
