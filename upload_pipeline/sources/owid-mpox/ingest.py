"""OWID Mpox ingest.

Pulls Our World in Data's compiled mpox (monkeypox) global daily series.
Aggregates national reports from 100+ countries into a single CSV. We retain
incident new_cases / new_deaths and the cumulative totals; per-million
derivatives are dropped (the dashboard recomputes from the kept columns).

Source: https://github.com/owid/monkeypox
File:   owid-monkeypox-data.csv
Cadence: daily (publication varies; many countries weekly)
Geography: countries + OWID aggregates (`World`, continents)
History: 2022-05 onward
"""
from __future__ import annotations

from io import StringIO
from pathlib import Path

import pandas as pd
import requests

CSV_URL = (
    "https://raw.githubusercontent.com/owid/monkeypox/main/owid-monkeypox-data.csv"
)


def fetch() -> pd.DataFrame:
    print(f"Downloading {CSV_URL}")
    resp = requests.get(CSV_URL, timeout=180)
    resp.raise_for_status()
    return pd.read_csv(StringIO(resp.text))


def iso3_to_iso2(code: str) -> str | None:
    import pycountry
    if not isinstance(code, str) or len(code) != 3:
        return None
    c = pycountry.countries.get(alpha_3=code)
    return c.alpha_2 if c else None


def parse_normalize(raw: pd.DataFrame) -> pd.DataFrame:
    df = raw.copy()
    df["location_id"] = df["iso_code"].apply(iso3_to_iso2)
    is_world = df["iso_code"] == "OWID_WRL"
    df.loc[is_world, "location_id"] = "WORLD"

    df["location_level"] = pd.Series(["national"] * len(df), dtype="object")
    df.loc[is_world, "location_level"] = "global"

    df = df[df["location_id"].notna()].copy()
    df = df.rename(columns={"location": "location_name"})
    df["date"] = pd.to_datetime(df["date"], utc=True, errors="raise")
    df["location_level"] = df["location_level"].astype("category")

    for col in ("new_cases", "new_deaths", "total_cases", "total_deaths"):
        df[col] = pd.to_numeric(df[col], errors="coerce")

    keep = ["date", "location_id", "location_level", "location_name",
            "new_cases", "new_deaths", "total_cases", "total_deaths"]
    df = df[keep]
    df = df.sort_values(["date", "location_id"]).reset_index(drop=True)
    return df


def main() -> None:
    raw = fetch()
    print(f"Raw rows: {len(raw):,}")
    df = parse_normalize(raw)
    print(f"After normalization: {len(df):,} rows × {len(df.columns)} cols")
    print(f"  date range: {df['date'].min().date()} → {df['date'].max().date()}")
    print(f"  locations: {df['location_id'].nunique()}")

    out_dir = Path(__file__).parent / "data"
    out_dir.mkdir(exist_ok=True)
    out_path = out_dir / "owid-mpox.parquet"
    df.to_parquet(out_path, index=False)
    print(f"Wrote {out_path} ({out_path.stat().st_size / 1024:.1f} KB)")


if __name__ == "__main__":
    main()
