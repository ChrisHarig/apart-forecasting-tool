"""WHO Global TB — annual incidence/mortality estimates by country.

Pulls the WHO TB programme's estimates CSV (one row per country-year). This is
annual cadence and is best used as a slow covariate or for comparison rather
than nowcasting. Single CSV, ~5k rows.

Source: https://www.who.int/teams/global-programme-on-tuberculosis-and-lung-health/data
File:   https://extranet.who.int/tme/generateCSV.asp?ds=estimates
Cadence: annual
Geography: 215 countries
History: 2000+
"""
from __future__ import annotations

from io import StringIO
from pathlib import Path

import pandas as pd
import requests

CSV_URL = "https://extranet.who.int/tme/generateCSV.asp?ds=estimates"

VALUE_COLUMNS = [
    "e_pop_num",       # population estimate
    "e_inc_100k",      # incidence rate per 100k
    "e_inc_num",       # absolute incidence
    "e_mort_100k",     # mortality rate per 100k (TB total)
    "e_mort_num",      # absolute mortality
    "e_tbhiv_prct",    # % of TB cases with HIV co-infection
    "c_cdr",           # case detection rate
]


def fetch() -> pd.DataFrame:
    print(f"Downloading {CSV_URL}")
    resp = requests.get(CSV_URL, timeout=180)
    resp.raise_for_status()
    return pd.read_csv(StringIO(resp.text), low_memory=False)


def parse_normalize(raw: pd.DataFrame) -> pd.DataFrame:
    df = raw.copy()
    # Annual: assign date as Dec 31 of the year.
    df["date"] = pd.to_datetime(df["year"].astype(int).astype(str) + "-12-31", utc=True)

    df["location_id"] = df["iso2"]
    df = df[df["location_id"].str.match(r"^[A-Z]{2}$", na=False)].copy()
    df["location_level"] = pd.Categorical(
        ["national"] * len(df), categories=["national"]
    )
    df = df.rename(columns={"country": "location_name"})

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
    print(f"  countries: {df['location_id'].nunique()}")

    out_dir = Path(__file__).parent / "data"
    out_dir.mkdir(exist_ok=True)
    out_path = out_dir / "who-tb-burden.parquet"
    df.to_parquet(out_path, index=False)
    print(f"Wrote {out_path} ({out_path.stat().st_size / 1024:.1f} KB)")


if __name__ == "__main__":
    main()
