"""Delphi `nchs_mortality` — weekly P&I and COVID-19 death certificates.

NCHS publishes weekly counts of death certificates listing pneumonia,
influenza, and COVID-19 as cause-of-death. The Delphi `nchs_mortality`
endpoint mirrors this with vintaged history.

Source: https://api.delphi.cmu.edu/epidata/nchs_mortality/
Cadence: weekly
Geography: US national + 10 HHS regions + 50 states
History: 2013-W40+ (P&I), 2020-W04+ (COVID)
"""
from __future__ import annotations

import time as _time
from datetime import datetime, time, timezone
from pathlib import Path

import pandas as pd
import requests
from epiweeks import Week

ENDPOINT = "https://api.delphi.cmu.edu/epidata/nchs_mortality/"
START_EPIWEEK = "201340"
END_EPIWEEK = "202599"

# NCHS uses lower-case state postal abbreviations and 'us' for national.
STATE_TO_LOCATION: dict[str, tuple[str, str]] = {
    "us": ("US", "national"),
    "al": ("01", "subnational-state"), "ak": ("02", "subnational-state"),
    "az": ("04", "subnational-state"), "ar": ("05", "subnational-state"),
    "ca": ("06", "subnational-state"), "co": ("08", "subnational-state"),
    "ct": ("09", "subnational-state"), "de": ("10", "subnational-state"),
    "dc": ("11", "subnational-state"), "fl": ("12", "subnational-state"),
    "ga": ("13", "subnational-state"), "hi": ("15", "subnational-state"),
    "id": ("16", "subnational-state"), "il": ("17", "subnational-state"),
    "in": ("18", "subnational-state"), "ia": ("19", "subnational-state"),
    "ks": ("20", "subnational-state"), "ky": ("21", "subnational-state"),
    "la": ("22", "subnational-state"), "me": ("23", "subnational-state"),
    "md": ("24", "subnational-state"), "ma": ("25", "subnational-state"),
    "mi": ("26", "subnational-state"), "mn": ("27", "subnational-state"),
    "ms": ("28", "subnational-state"), "mo": ("29", "subnational-state"),
    "mt": ("30", "subnational-state"), "ne": ("31", "subnational-state"),
    "nv": ("32", "subnational-state"), "nh": ("33", "subnational-state"),
    "nj": ("34", "subnational-state"), "nm": ("35", "subnational-state"),
    "ny": ("36", "subnational-state"), "nc": ("37", "subnational-state"),
    "nd": ("38", "subnational-state"), "oh": ("39", "subnational-state"),
    "ok": ("40", "subnational-state"), "or": ("41", "subnational-state"),
    "pa": ("42", "subnational-state"), "ri": ("44", "subnational-state"),
    "sc": ("45", "subnational-state"), "sd": ("46", "subnational-state"),
    "tn": ("47", "subnational-state"), "tx": ("48", "subnational-state"),
    "ut": ("49", "subnational-state"), "vt": ("50", "subnational-state"),
    "va": ("51", "subnational-state"), "wa": ("53", "subnational-state"),
    "wv": ("54", "subnational-state"), "wi": ("55", "subnational-state"),
    "wy": ("56", "subnational-state"),
}

VALUE_COLUMNS = [
    "covid_19_deaths",
    "total_deaths",
    "percent_of_expected_deaths",
    "pneumonia_deaths",
    "pneumonia_and_covid_19_deaths",
    "influenza_deaths",
    "pneumonia_influenza_or_covid_19_deaths",
]


def epiweek_to_period_end(epiweek_int: int) -> datetime:
    year = epiweek_int // 100
    week = epiweek_int % 100
    return datetime.combine(Week(year, week).enddate(), time.min, tzinfo=timezone.utc)


def fetch_state(state: str) -> list[dict]:
    params = {"locations": state, "epiweeks": f"{START_EPIWEEK}-{END_EPIWEEK}"}
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
            raise RuntimeError(f"Delphi error {state!r}: {payload.get('message')}")
        return payload.get("epidata", []) or []
    raise RuntimeError(f"429 retries exhausted for {state!r}")


def parse_normalize(raw: list[dict]) -> pd.DataFrame:
    df = pd.DataFrame(raw)
    # Some payload variants put the date in `start_week` or `time_value`.
    if "epiweek" in df.columns:
        df["date"] = df["epiweek"].apply(epiweek_to_period_end)
    elif "time_value" in df.columns:
        df["date"] = df["time_value"].apply(
            lambda x: epiweek_to_period_end(int(x)) if pd.notna(x) else pd.NaT
        )
    df["date"] = pd.to_datetime(df["date"], utc=True)

    mapping = df["state"].map(STATE_TO_LOCATION) if "state" in df.columns \
              else df["geo_value"].map(STATE_TO_LOCATION)
    df["location_id"] = mapping.map(lambda t: t[0])
    df["location_level"] = mapping.map(lambda t: t[1]).astype("category")
    df = df.rename(columns={"state": "location_name"} if "state" in df.columns
                   else {"geo_value": "location_name"})

    for col in VALUE_COLUMNS:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    keep = ["date", "location_id", "location_level", "location_name"]
    keep.extend(c for c in VALUE_COLUMNS if c in df.columns)
    df = df[keep].copy()
    df = df.sort_values(["date", "location_id"]).reset_index(drop=True)
    return df


def main() -> None:
    print(f"Fetching Delphi nchs_mortality ({len(STATE_TO_LOCATION)} locations)")
    rows: list[dict] = []
    for state in STATE_TO_LOCATION:
        page = fetch_state(state)
        rows.extend(page)
        print(f"  {state}: {len(page):,}")
        _time.sleep(1.0)

    print(f"\nTotal raw rows: {len(rows):,}")
    df = parse_normalize(rows)
    print(f"After normalization: {len(df):,} rows × {len(df.columns)} cols")
    print(f"  date range: {df['date'].min().date()} → {df['date'].max().date()}")

    out_dir = Path(__file__).parent / "data"
    out_dir.mkdir(exist_ok=True)
    out_path = out_dir / "delphi-nchs-mortality.parquet"
    df.to_parquet(out_path, index=False)
    print(f"Wrote {out_path}")


if __name__ == "__main__":
    main()
