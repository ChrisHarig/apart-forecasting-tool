"""Delphi `fluview_clinical` — clinical-laboratory flu virology weekly.

The clinical-labs companion to ILINet. Each row is (epiweek, region) with the
total specimens tested and the % positive for influenza (A/B). This is the
go-to "is the lab signal up?" series; pair with ILINet's symptomatic %ILI for
the standard flu nowcasting setup.

Source: https://api.delphi.cmu.edu/epidata/fluview_clinical/
Cadence: weekly
Geography: national + 10 HHS regions + 50 states
History: 2015-W40 onward
"""
from __future__ import annotations

import time as _time
from datetime import datetime, time, timezone
from pathlib import Path

import pandas as pd
import requests
from epiweeks import Week

ENDPOINT = "https://api.delphi.cmu.edu/epidata/fluview_clinical/"
START_EPIWEEK = "201540"
END_EPIWEEK = "202599"

# Same region codes as the parent fluview endpoint. We re-use the mapping.
DELPHI_REGION_TO_LOCATION: dict[str, tuple[str, str]] = {
    "nat": ("US", "national"),
    **{f"hhs{n}": (f"US-HHS-{n}", "subnational-region") for n in range(1, 11)},
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
    "total_specimens",
    "total_a",
    "total_b",
    "percent_positive",
    "percent_a",
    "percent_b",
]


def epiweek_to_period_end(epiweek_int: int) -> datetime:
    year = epiweek_int // 100
    week = epiweek_int % 100
    return datetime.combine(Week(year, week).enddate(), time.min, tzinfo=timezone.utc)


def fetch_region(region: str) -> list[dict]:
    params = {"regions": region, "epiweeks": f"{START_EPIWEEK}-{END_EPIWEEK}"}
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
            raise RuntimeError(f"Delphi error {region!r}: {payload.get('message')}")
        return payload.get("epidata", []) or []
    raise RuntimeError(f"429 retries exhausted for {region!r}")


def parse_normalize(raw: list[dict]) -> pd.DataFrame:
    df = pd.DataFrame(raw)
    df["date"] = df["epiweek"].apply(epiweek_to_period_end)
    df["date"] = pd.to_datetime(df["date"], utc=True)
    mapping = df["region"].map(DELPHI_REGION_TO_LOCATION)
    df["location_id"] = mapping.map(lambda t: t[0])
    df["location_level"] = mapping.map(lambda t: t[1]).astype("category")
    df = df.rename(columns={"region": "location_name"})

    for col in VALUE_COLUMNS:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    keep = ["date", "location_id", "location_level", "location_name"]
    keep.extend(c for c in VALUE_COLUMNS if c in df.columns)
    df = df[keep].copy()
    df = df.sort_values(["date", "location_id"]).reset_index(drop=True)
    return df


def main() -> None:
    print(f"Fetching Delphi fluview_clinical ({len(DELPHI_REGION_TO_LOCATION)} regions)")
    rows: list[dict] = []
    for region in DELPHI_REGION_TO_LOCATION:
        page = fetch_region(region)
        rows.extend(page)
        print(f"  {region}: {len(page):,}")
        _time.sleep(1.0)

    print(f"\nTotal raw rows: {len(rows):,}")
    df = parse_normalize(rows)
    print(f"After normalization: {len(df):,} rows × {len(df.columns)} cols")
    print(f"  date range: {df['date'].min().date()} → {df['date'].max().date()}")

    out_dir = Path(__file__).parent / "data"
    out_dir.mkdir(exist_ok=True)
    out_path = out_dir / "delphi-fluview-clinical.parquet"
    df.to_parquet(out_path, index=False)
    print(f"Wrote {out_path} ({out_path.stat().st_size / 1024:.1f} KB)")


if __name__ == "__main__":
    main()
