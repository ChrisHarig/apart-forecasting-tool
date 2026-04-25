"""NHSN HRD ingest module.

Pulls weekly hospital respiratory data from CDC's Socrata endpoint and
normalizes it into the EPI-Eval row-level convention (date, location_id,
location_level, value cols).

Source: https://data.cdc.gov/resource/ua7e-t2fy
Cadence: weekly (period-end Saturday, MMWR week)
Geography: 50 states + DC + 5 territories + national aggregate

The source has 213 columns; we keep ~14 of the most useful ones (FluSight
target columns + bed capacity + per-100k rates + cumulative seasonal sums).
Other columns can be added later by editing VALUE_COLUMNS below — the
schema validator will catch any mismatch with card.yaml.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import requests

SOCRATA_ENDPOINT = "https://data.cdc.gov/resource/ua7e-t2fy.json"
PAGE_SIZE = 50000

VALUE_COLUMNS = [
    "totalconfflunewadm",
    "totalconfc19newadm",
    "totalconfrsvnewadm",
    "numinptbeds",
    "numinptbedsocc",
    "numicubeds",
    "numicubedsocc",
    "totalconfc19icupats",
    "totalconffluicupats",
    "totalconfflunewadmper100k",
    "totalconfc19newadmper100k",
    "totalconfflunewadmcumulativeseasonalsum",
    "totalconfc19newadmcumulativeseasonalsum",
    "totalconfrsvnewadmcumulativeseasonalsum",
]

# Source jurisdiction → canonical location_id.
#  - States/DC: 2-digit FIPS
#  - Territories: 2-digit FIPS
#  - National aggregate: "US"
#  - HHS regions: "US-HHS-N" (no FIPS exists for these; following the
#    schema's "country prefix + native code" rule for sub-national levels
#    that don't fit any standard code system)
JURISDICTION_TO_LOCATION_ID: dict[str, str] = {
    # States + DC
    "AL": "01", "AK": "02", "AZ": "04", "AR": "05", "CA": "06",
    "CO": "08", "CT": "09", "DE": "10", "DC": "11", "FL": "12",
    "GA": "13", "HI": "15", "ID": "16", "IL": "17", "IN": "18",
    "IA": "19", "KS": "20", "KY": "21", "LA": "22", "ME": "23",
    "MD": "24", "MA": "25", "MI": "26", "MN": "27", "MS": "28",
    "MO": "29", "MT": "30", "NE": "31", "NV": "32", "NH": "33",
    "NJ": "34", "NM": "35", "NY": "36", "NC": "37", "ND": "38",
    "OH": "39", "OK": "40", "OR": "41", "PA": "42", "RI": "44",
    "SC": "45", "SD": "46", "TN": "47", "TX": "48", "UT": "49",
    "VT": "50", "VA": "51", "WA": "53", "WV": "54", "WI": "55",
    "WY": "56",
    # Territories
    "AS": "60", "GU": "66", "MP": "69", "PR": "72", "VI": "78",
    # National
    "USA": "US",
    # HHS regions
    **{f"Region {n}": f"US-HHS-{n}" for n in range(1, 11)},
}


def _location_level(jurisdiction: str) -> str:
    if jurisdiction == "USA":
        return "national"
    if jurisdiction.startswith("Region "):
        return "subnational-region"
    return "subnational-state"


def fetch() -> list[dict]:
    """Page through the Socrata endpoint and return raw row dicts."""
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


def parse_normalize(raw: list[dict]) -> pd.DataFrame:
    """Normalize raw Socrata rows into the EPI-Eval row-level convention.

    Returns a DataFrame with columns:
      date, location_id, location_level, location_name, [respseason], <value cols>
    """
    df = pd.DataFrame(raw)

    df = df.rename(columns={"weekendingdate": "date", "jurisdiction": "location_name"})

    df["date"] = pd.to_datetime(df["date"], utc=True, errors="raise")

    df["location_id"] = df["location_name"].map(JURISDICTION_TO_LOCATION_ID)
    unmapped = df.loc[df["location_id"].isna(), "location_name"].unique()
    if len(unmapped) > 0:
        raise ValueError(
            f"Unmapped jurisdictions (extend JURISDICTION_TO_LOCATION_ID): {sorted(unmapped.tolist())}"
        )

    df["location_level"] = df["location_name"].map(_location_level).astype("category")

    for col in VALUE_COLUMNS:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
        else:
            print(f"WARN: expected column {col!r} not in source response", file=sys.stderr)

    keep = ["date", "location_id", "location_level", "location_name"]
    if "respseason" in df.columns:
        keep.append("respseason")
    keep.extend(c for c in VALUE_COLUMNS if c in df.columns)
    df = df[keep].copy()

    df = df.sort_values(["date", "location_id"]).reset_index(drop=True)

    return df


def main() -> None:
    print(f"Fetching {SOCRATA_ENDPOINT} ...")
    raw = fetch()
    print(f"  fetched {len(raw):,} rows")

    df = parse_normalize(raw)
    print(f"After normalization: {len(df):,} rows × {len(df.columns)} columns")
    print(f"  date range: {df['date'].min().date()} → {df['date'].max().date()}")
    print(f"  unique locations: {df['location_id'].nunique()}")
    level_counts = df["location_level"].value_counts().to_dict()
    print(f"  location_level breakdown: {level_counts}")
    print()
    print("First 3 rows of FluSight target columns:")
    cols = ["date", "location_id", "location_name",
            "totalconfflunewadm", "totalconfc19newadm", "totalconfrsvnewadm"]
    print(df[cols].head(3).to_string(index=False))

    out_dir = Path(__file__).parent / "data"
    out_dir.mkdir(exist_ok=True)
    out_path = out_dir / "nhsn-hrd.parquet"
    df.to_parquet(out_path, index=False)
    size_mb = out_path.stat().st_size / 1024 / 1024
    print(f"\nWrote {out_path} ({size_mb:.2f} MB)")


if __name__ == "__main__":
    main()
