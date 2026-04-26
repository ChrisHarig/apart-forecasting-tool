"""HHS Protect (historical) — daily US state hosp capacity 2020-07 → 2024-10.

Pulls the COVID-19 Reported Patient Impact and Hospital Capacity by State
Time-Series view from healthdata.gov. Daily rows per state with bed
capacity / occupancy / admissions / staffing-shortage flags.

This is the predecessor of NHSN HRD; the schemas are different (HHS Protect
was voluntary daily, NHSN HRD is mandatory weekly). Mark `succeeded_by` so the
dashboard knows not to splice them.

Source: https://healthdata.gov/Hospital/COVID-19-Reported-Patient-Impact-and-Hospital-Capa/g62h-syeh
Cadence: daily
Geography: US states + DC + territories
History: 2020-07 → 2024-10 (now inactive; superseded by NHSN HRD)
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd
import requests

ENDPOINT = "https://healthdata.gov/resource/g62h-syeh.json"
PAGE_SIZE = 50000

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
    "inpatient_beds",
    "inpatient_beds_used",
    "inpatient_beds_used_covid",
    "previous_day_admission_adult_covid_confirmed",
    "previous_day_admission_adult_covid_suspected",
    "previous_day_admission_pediatric_covid_confirmed",
    "previous_day_admission_pediatric_covid_suspected",
    "staffed_adult_icu_bed_occupancy",
    "staffed_icu_adult_patients_confirmed_and_suspected_covid",
    "total_adult_patients_hospitalized_confirmed_and_suspected_covid",
    "total_pediatric_patients_hospitalized_confirmed_and_suspected_covid",
    "deaths_covid",
]


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
        print(f"  offset={offset:,} total={len(rows):,}")
        if len(page) < PAGE_SIZE:
            break
    return rows


def parse_normalize(raw: list[dict]) -> pd.DataFrame:
    df = pd.DataFrame(raw)
    df["date"] = pd.to_datetime(df["date"], utc=True, errors="raise")

    df["location_id"] = df["state"].map(US_POSTAL_TO_FIPS)
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
    print(f"\nTotal raw rows: {len(raw):,}")
    df = parse_normalize(raw)
    print(f"After normalization: {len(df):,} rows × {len(df.columns)} cols")
    print(f"  date range: {df['date'].min().date()} → {df['date'].max().date()}")

    out_dir = Path(__file__).parent / "data"
    out_dir.mkdir(exist_ok=True)
    out_path = out_dir / "hhs-protect-historical.parquet"
    df.to_parquet(out_path, index=False)
    print(f"Wrote {out_path} ({out_path.stat().st_size / 1024 / 1024:.2f} MB)")


if __name__ == "__main__":
    main()
