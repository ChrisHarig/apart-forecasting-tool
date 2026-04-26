"""COVID Tracking Project — US states daily (archived 2021-03).

The volunteer-run COVID Tracking Project published a single all-states-history
CSV. The series spans 2020-01 through 2021-03-07 with cases, tests, current
hospitalizations, ICU, ventilator, and death counts per state per day.

Source: https://covidtracking.com
File:   https://covidtracking.com/data/download/all-states-history.csv
Cadence: daily
Geography: 56 US jurisdictions (states + DC + territories)
History: 2020-01-13 → 2021-03-07
"""
from __future__ import annotations

from io import StringIO
from pathlib import Path

import pandas as pd
import requests

CSV_URL = "https://covidtracking.com/data/download/all-states-history.csv"

US_POSTAL_TO_FIPS = {
    "AL": "01", "AK": "02", "AZ": "04", "AR": "05", "CA": "06", "CO": "08",
    "CT": "09", "DE": "10", "DC": "11", "FL": "12", "GA": "13", "HI": "15",
    "ID": "16", "IL": "17", "IN": "18", "IA": "19", "KS": "20", "KY": "21",
    "LA": "22", "ME": "23", "MD": "24", "MA": "25", "MI": "26", "MN": "27",
    "MS": "28", "MO": "29", "MT": "30", "NE": "31", "NV": "32", "NH": "33",
    "NJ": "34", "NM": "35", "NY": "36", "NC": "37", "ND": "38", "OH": "39",
    "OK": "40", "OR": "41", "PA": "42", "RI": "44", "SC": "45", "SD": "46",
    "TN": "47", "TX": "48", "UT": "49", "VT": "50", "VA": "51", "WA": "53",
    "WV": "54", "WI": "55", "WY": "56",
    "PR": "72", "VI": "78", "GU": "66", "AS": "60", "MP": "69",
}

VALUE_COLUMNS = [
    "positive",                # cumulative confirmed cases
    "death",                   # cumulative deaths
    "hospitalizedCurrently",   # current hospital census
    "inIcuCurrently",          # current ICU census
    "onVentilatorCurrently",   # current ventilator census
    "totalTestResults",        # cumulative tests
    "positiveIncrease",        # daily new cases
    "deathIncrease",           # daily new deaths
    "hospitalizedIncrease",    # daily new admissions
    "totalTestResultsIncrease",# daily new tests
]


def fetch() -> pd.DataFrame:
    print(f"Downloading {CSV_URL}")
    resp = requests.get(CSV_URL, timeout=120)
    resp.raise_for_status()
    return pd.read_csv(StringIO(resp.text))


def parse_normalize(raw: pd.DataFrame) -> pd.DataFrame:
    df = raw.copy()
    df["date"] = pd.to_datetime(df["date"], utc=True, errors="raise")

    df["location_id"] = df["state"].map(US_POSTAL_TO_FIPS)
    unmapped = df[df["location_id"].isna()]["state"].unique()
    if len(unmapped):
        print(f"  WARN unmapped state codes dropped: {sorted(unmapped.tolist())}")
        df = df.dropna(subset=["location_id"]).copy()

    df["location_level"] = pd.Categorical(
        ["subnational-state"] * len(df), categories=["subnational-state"]
    )
    df = df.rename(columns={"state": "location_name"})

    for col in VALUE_COLUMNS:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    keep = ["date", "location_id", "location_level", "location_name"]
    keep.extend(c for c in VALUE_COLUMNS if c in df.columns)
    df = df[keep].copy()
    df = df.sort_values(["date", "location_id"]).reset_index(drop=True)
    return df


def main() -> None:
    raw = fetch()
    print(f"Raw rows: {len(raw):,}")
    df = parse_normalize(raw)
    print(f"After normalization: {len(df):,} rows × {len(df.columns)} cols")
    print(f"  date range: {df['date'].min().date()} → {df['date'].max().date()}")
    print(f"  jurisdictions: {df['location_id'].nunique()}")

    out_dir = Path(__file__).parent / "data"
    out_dir.mkdir(exist_ok=True)
    out_path = out_dir / "covid-tracking-project.parquet"
    df.to_parquet(out_path, index=False)
    print(f"Wrote {out_path} ({out_path.stat().st_size / 1024:.1f} KB)")


if __name__ == "__main__":
    main()
