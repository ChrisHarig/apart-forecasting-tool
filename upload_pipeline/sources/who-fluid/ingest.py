"""WHO FluID — global weekly ILI / SARI rates by country.

WHO's xMart `VIW_FID` view. Each row is (country, ISO week) with denominators
+ ILI/SARI counts. Pagination matches FluNet.

Source: https://xmart-api-public.who.int/FLUMART/VIW_FID
Cadence: weekly
Geography: 60+ countries
History: ~2010 onward (varies)
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd
import requests

ENDPOINT = "https://xmart-api-public.who.int/FLUMART/VIW_FID"
PAGE_SIZE = 50000

VALUE_COLUMNS = [
    "ILI_CASE",          # ILI cases
    "ILI_OUTPATIENTS",   # outpatient denominator
    "SARI_CASE",         # SARI cases
    "SARI_INPATIENTS",   # inpatient denominator
    "ARI_CASE", "ARI_OUTPATIENTS",
    "PNEU_CASE", "PNEU_DEATHS",
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
    df["date"] = pd.to_datetime(df.get("ISO_WEEKSTARTDATE"), utc=True, errors="coerce")
    df = df.dropna(subset=["date"]).copy()
    df["date"] = df["date"] + pd.Timedelta(days=6)

    df["location_id"] = df["ISO2"].astype(str).str.upper()
    df = df[df["location_id"].str.match(r"^[A-Z]{2}$", na=False)].copy()
    df["location_level"] = pd.Categorical(["national"] * len(df), categories=["national"])
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
    raw = fetch()
    print(f"\nTotal raw rows: {len(raw):,}")
    df = parse_normalize(raw)
    print(f"After normalization: {len(df):,} rows × {len(df.columns)} cols")
    print(f"  date range: {df['date'].min().date()} → {df['date'].max().date()}")

    out_dir = Path(__file__).parent / "data"
    out_dir.mkdir(exist_ok=True)
    out_path = out_dir / "who-fluid.parquet"
    df.to_parquet(out_path, index=False)
    print(f"Wrote {out_path}")


if __name__ == "__main__":
    main()
