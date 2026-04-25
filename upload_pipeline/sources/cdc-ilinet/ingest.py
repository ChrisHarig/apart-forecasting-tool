"""CDC ILINet (FluView) ingest module.

Pulls weighted ILI percentages and provider counts from Delphi epidata
`fluview` endpoint. Returns the latest revision per (epiweek, region);
the vintaged history would be a separate `cdc-ilinet-vintaged` source
that pulls each historical issue.

Source: https://api.delphi.cmu.edu/epidata/fluview/
Cadence: weekly (MMWR week, period-end Saturday)
Geography: national + 10 HHS regions + 50 states + DC + 4 territories
History: 1997-W40 onward
"""
from __future__ import annotations

import sys
import time as _time
from datetime import datetime, time, timezone
from pathlib import Path

import pandas as pd
import requests
from epiweeks import Week

REQUEST_DELAY_SEC = 1.0  # polite spacing between Delphi calls
MAX_RETRIES_ON_429 = 5

DELPHI_ENDPOINT = "https://api.delphi.cmu.edu/epidata/fluview/"
START_EPIWEEK = "199740"
END_EPIWEEK = "202599"

VALUE_COLUMNS = [
    "wili",            # weighted % ILI — primary signal
    "ili",             # unweighted % ILI
    "num_ili",         # ILI patient count
    "num_patients",    # total patient count (denominator)
    "num_providers",   # number of reporting providers (data quality)
]

# Delphi region code → (location_id, location_level).
# State codes are lowercase 2-letter postal abbreviations.
DELPHI_REGION_TO_LOCATION: dict[str, tuple[str, str]] = {
    "nat": ("US", "national"),
    **{f"hhs{n}": (f"US-HHS-{n}", "subnational-region") for n in range(1, 11)},
    # 50 states + DC
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
    # Territories
    "pr": ("72", "subnational-state"), "vi": ("78", "subnational-state"),
    "gu": ("66", "subnational-state"), "as": ("60", "subnational-state"),
    "mp": ("69", "subnational-state"),
}

# Skipped: cen1..9 (Census regions duplicate HHS coverage),
# ny_minus_jfk (non-canonical NY excluding NYC).
SKIP_REGIONS = {f"cen{n}" for n in range(1, 10)} | {"ny_minus_jfk"}


def epiweek_to_period_end(epiweek_int: int) -> datetime:
    """Convert an MMWR epiweek (YYYYWW) to its period-end Saturday at UTC midnight."""
    year = epiweek_int // 100
    week = epiweek_int % 100
    w = Week(year, week)
    return datetime.combine(w.enddate(), time.min, tzinfo=timezone.utc)


def fetch_region(region: str) -> list[dict]:
    """Fetch all epiweeks for one region. Retries on 429 with exponential backoff."""
    params = {"regions": region, "epiweeks": f"{START_EPIWEEK}-{END_EPIWEEK}"}
    delay = 1.0
    for attempt in range(MAX_RETRIES_ON_429):
        resp = requests.get(DELPHI_ENDPOINT, params=params, timeout=120)
        if resp.status_code == 429:
            retry_after = float(resp.headers.get("Retry-After", delay))
            print(f"  [429] backing off {retry_after:.0f}s for region {region!r}")
            _time.sleep(retry_after)
            delay *= 2
            continue
        resp.raise_for_status()
        payload = resp.json()
        if payload.get("result") == -2:
            return []
        if payload.get("result") != 1:
            raise RuntimeError(
                f"Delphi error for region {region!r}: {payload.get('message')}"
            )
        return payload.get("epidata", []) or []
    raise RuntimeError(f"Exceeded retries on 429 for region {region!r}")


def fetch() -> list[dict]:
    """Fetch every region in our mapping. ~66 polite API calls."""
    rows: list[dict] = []
    for region in DELPHI_REGION_TO_LOCATION:
        page = fetch_region(region)
        rows.extend(page)
        print(f"  {region}: {len(page):,} rows")
        _time.sleep(REQUEST_DELAY_SEC)
    return rows


def parse_normalize(raw: list[dict]) -> pd.DataFrame:
    df = pd.DataFrame(raw)

    # Drop the regions we explicitly skip (in case the API ever returns them).
    df = df[~df["region"].isin(SKIP_REGIONS)].copy()

    # epiweek (YYYYWW int) → date (period-end Saturday, UTC).
    df["date"] = df["epiweek"].apply(epiweek_to_period_end)
    df["date"] = pd.to_datetime(df["date"], utc=True)

    # region → location_id, location_level.
    mapping = df["region"].map(DELPHI_REGION_TO_LOCATION)
    unmapped = df.loc[mapping.isna(), "region"].unique()
    if len(unmapped) > 0:
        raise ValueError(
            f"Unmapped Delphi regions (extend DELPHI_REGION_TO_LOCATION): "
            f"{sorted(unmapped.tolist())}"
        )
    df["location_id"] = mapping.map(lambda t: t[0])
    df["location_level"] = mapping.map(lambda t: t[1]).astype("category")

    # Source's region code is useful for traceability.
    df = df.rename(columns={"region": "location_name"})

    # Ensure value columns are numeric (Delphi returns them numeric already, but coerce defensively).
    for col in VALUE_COLUMNS:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    # Subset to the columns we keep.
    keep = ["date", "location_id", "location_level", "location_name"]
    keep.extend(c for c in VALUE_COLUMNS if c in df.columns)
    df = df[keep].copy()

    df = df.sort_values(["date", "location_id"]).reset_index(drop=True)
    return df


def main() -> None:
    print(f"Fetching Delphi fluview ({len(DELPHI_REGION_TO_LOCATION)} regions) ...")
    raw = fetch()
    print(f"\nTotal raw rows: {len(raw):,}")

    df = parse_normalize(raw)
    print(f"After normalization: {len(df):,} rows × {len(df.columns)} columns")
    print(f"  date range: {df['date'].min().date()} → {df['date'].max().date()}")
    print(f"  unique locations: {df['location_id'].nunique()}")
    print(f"  level breakdown: {df['location_level'].value_counts().to_dict()}")
    print()
    print("Sample rows (recent national):")
    sample = df[df["location_id"] == "US"].tail(3)
    print(sample[["date", "location_id", "wili", "ili", "num_providers"]].to_string(index=False))

    out_dir = Path(__file__).parent / "data"
    out_dir.mkdir(exist_ok=True)
    out_path = out_dir / "cdc-ilinet.parquet"
    df.to_parquet(out_path, index=False)
    print(f"\nWrote {out_path} ({out_path.stat().st_size / 1024 / 1024:.2f} MB)")


if __name__ == "__main__":
    main()
