"""Delphi `flusurv` — CDC FluSurv-NET weekly hospitalisation rates.

Pulls per-state and overall (ENT/MAT/etc.) flu hospitalisation rates from the
Delphi `flusurv` endpoint. Each location is a CDC catchment, not a US state in
the FIPS sense — the location codes (`network_all`, `CA`, `CO`, etc.) are
state-postal-style for the 14 RESP-NET sites plus a network-wide aggregate.

Source: https://api.delphi.cmu.edu/epidata/flusurv/
Cadence: weekly (epiweek period-end Saturday)
Geography: 14 RESP-NET catchments + network-all aggregate
History: 2003-W40 onward
"""
from __future__ import annotations

import time as _time
from datetime import datetime, time, timezone
from pathlib import Path

import pandas as pd
import requests
from epiweeks import Week

ENDPOINT = "https://api.delphi.cmu.edu/epidata/flusurv/"
START_EPIWEEK = "200340"
END_EPIWEEK = "202599"

# FluSurv-NET catchments. `network_all` is the network-wide aggregate.
# State codes here are FluSurv-NET catchment codes — they happen to match
# US state postal abbreviations but each represents a *catchment* within
# the state, not the whole state.
LOCATIONS = [
    "network_all",
    "CA", "CO", "CT", "GA", "MD", "MI", "MN", "NM", "NY_albany",
    "NY_rochester", "OR", "TN", "UT",
]

# Catchment code → (location_id, location_level). Use `subnational-region`
# with a synthetic prefix `US-FLUSURV-<code>` because these are CDC
# catchments, not first-level admin units.
CATCHMENT_TO_LOCATION = {
    code: (f"US-FLUSURV-{code.upper().replace('_', '-')}", "subnational-region")
    for code in LOCATIONS
}
CATCHMENT_TO_LOCATION["network_all"] = ("US-FLUSURV-ALL", "subnational-region")

VALUE_COLUMNS = [
    "rate_overall",         # weekly hosp rate per 100k, all ages
    "rate_age_0",           # 0-4
    "rate_age_1",           # 5-17
    "rate_age_2",           # 18-49
    "rate_age_3",           # 50-64
    "rate_age_4",           # 65+
]


def fetch_one(loc: str) -> list[dict]:
    params = {"locations": loc, "epiweeks": f"{START_EPIWEEK}-{END_EPIWEEK}"}
    delay = 1.0
    for _ in range(5):
        resp = requests.get(ENDPOINT, params=params, timeout=120)
        if resp.status_code == 429:
            _time.sleep(delay)
            delay *= 2
            continue
        resp.raise_for_status()
        payload = resp.json()
        if payload.get("result") == -2:
            return []
        if payload.get("result") != 1:
            raise RuntimeError(f"Delphi error {loc!r}: {payload.get('message')}")
        return payload.get("epidata", []) or []
    raise RuntimeError(f"429 retries exhausted for {loc!r}")


def epiweek_to_period_end(epiweek_int: int) -> datetime:
    year = epiweek_int // 100
    week = epiweek_int % 100
    return datetime.combine(Week(year, week).enddate(), time.min, tzinfo=timezone.utc)


def parse_normalize(raw: list[dict]) -> pd.DataFrame:
    df = pd.DataFrame(raw)
    df["date"] = df["epiweek"].apply(epiweek_to_period_end)
    df["date"] = pd.to_datetime(df["date"], utc=True)

    mapping = df["location"].map(CATCHMENT_TO_LOCATION)
    df["location_id"] = mapping.map(lambda t: t[0])
    df["location_level"] = mapping.map(lambda t: t[1]).astype("category")
    df = df.rename(columns={"location": "location_name"})

    for col in VALUE_COLUMNS:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    keep = ["date", "location_id", "location_level", "location_name"]
    keep.extend(c for c in VALUE_COLUMNS if c in df.columns)
    df = df[keep].copy()
    df = df.sort_values(["date", "location_id"]).reset_index(drop=True)
    return df


def main() -> None:
    print(f"Fetching Delphi flusurv ({len(LOCATIONS)} catchments)")
    rows: list[dict] = []
    for loc in LOCATIONS:
        page = fetch_one(loc)
        rows.extend(page)
        print(f"  {loc}: {len(page):,} rows")
        _time.sleep(1.0)

    print(f"\nTotal raw rows: {len(rows):,}")
    df = parse_normalize(rows)
    print(f"After normalization: {len(df):,} rows × {len(df.columns)} cols")
    print(f"  date range: {df['date'].min().date()} → {df['date'].max().date()}")

    out_dir = Path(__file__).parent / "data"
    out_dir.mkdir(exist_ok=True)
    out_path = out_dir / "delphi-flusurv.parquet"
    df.to_parquet(out_path, index=False)
    print(f"Wrote {out_path} ({out_path.stat().st_size / 1024:.1f} KB)")


if __name__ == "__main__":
    main()
