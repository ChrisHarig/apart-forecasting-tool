"""CDC NNDSS Weekly Data — long-format multi-condition notifiable diseases.

This Socrata view (`x9gk-5huc`) covers 2022+ digital NNDSS reporting. Each row
is (year, week, jurisdiction, label) with a current-week count `m2`. We emit
long-format rows: one per (date, location, condition).

Mapping `label` → EPI-Eval `condition` slug is partial — NNDSS has 120+ labels
and only a fraction map directly to our vocabulary. Unmapped labels are kept
in `condition_native` but the row-level `condition` is set to `unknown` so the
schema's `condition` + `condition_type` invariants still hold; downstream
filters can use `condition_native` for source-fidelity work.

Source: https://data.cdc.gov/NNDSS/NNDSS-Weekly-Data/x9gk-5huc
Cadence: weekly (epiweek)
Geography: US national + reporting jurisdictions (states + DC + territories +
           HHS-style "regions" like 'NEW ENGLAND')
History: 2022+ (this Socrata view; older NNDSS lives in legacy files)
"""
from __future__ import annotations

from datetime import datetime, time, timezone
from pathlib import Path

import pandas as pd
import requests
import yaml
from epiweeks import Week

ENDPOINT = "https://data.cdc.gov/resource/x9gk-5huc.json"
PAGE_SIZE = 50000

# Label-prefix → (slug, condition_type) mapping comes from the schema-side
# registry so adding a new label is a YAML edit, not a code change.
_REGISTRY_PATH = (
    Path(__file__).resolve().parent.parent.parent
    / "schema" / "nndss_label_mapping.yaml"
)


def _load_label_mapping() -> list[tuple[str, str, str]]:
    data = yaml.safe_load(_REGISTRY_PATH.read_text())
    return [(m["prefix"], m["slug"], m["type"]) for m in data["mappings"]]


LABEL_PREFIX_TO_CONDITION: list[tuple[str, str, str]] = _load_label_mapping()

# 50 states + DC + territories + national.
STATE_NAME_TO_FIPS = {
    "ALABAMA":"01", "ALASKA":"02", "ARIZONA":"04", "ARKANSAS":"05",
    "CALIFORNIA":"06", "COLORADO":"08", "CONNECTICUT":"09", "DELAWARE":"10",
    "DISTRICT OF COLUMBIA":"11", "D.C.":"11", "FLORIDA":"12", "GEORGIA":"13",
    "HAWAII":"15", "IDAHO":"16", "ILLINOIS":"17", "INDIANA":"18", "IOWA":"19",
    "KANSAS":"20", "KENTUCKY":"21", "LOUISIANA":"22", "MAINE":"23",
    "MARYLAND":"24", "MASSACHUSETTS":"25", "MICHIGAN":"26", "MINNESOTA":"27",
    "MISSISSIPPI":"28", "MISSOURI":"29", "MONTANA":"30", "NEBRASKA":"31",
    "NEVADA":"32", "NEW HAMPSHIRE":"33", "NEW JERSEY":"34", "NEW MEXICO":"35",
    "NEW YORK":"36", "NEW YORK CITY":"36-NYC", "NORTH CAROLINA":"37",
    "NORTH DAKOTA":"38", "OHIO":"39", "OKLAHOMA":"40", "OREGON":"41",
    "PENNSYLVANIA":"42", "RHODE ISLAND":"44", "SOUTH CAROLINA":"45",
    "SOUTH DAKOTA":"46", "TENNESSEE":"47", "TEXAS":"48", "UTAH":"49",
    "VERMONT":"50", "VIRGINIA":"51", "WASHINGTON":"53", "WEST VIRGINIA":"54",
    "WISCONSIN":"55", "WYOMING":"56",
    "AMERICAN SAMOA":"60", "GUAM":"66", "PUERTO RICO":"72", "U.S. VIRGIN ISLANDS":"78",
    "VIRGIN ISLANDS":"78", "NORTHERN MARIANA ISLANDS":"69", "CNMI":"69",
}
NATIONAL_NAMES = {"US RESIDENTS", "TOTAL", "U.S. RESIDENTS, EXCLUDING U.S. TERRITORIES"}


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


def epiweek_to_period_end(year: int, week: int) -> datetime:
    return datetime.combine(Week(year, week).enddate(), time.min, tzinfo=timezone.utc)


def map_label(label: str) -> tuple[str, str]:
    for prefix, slug, ctype in LABEL_PREFIX_TO_CONDITION:
        if label.startswith(prefix):
            return slug, ctype
    return "unknown", "pathogen"


def parse_normalize(raw: list[dict]) -> pd.DataFrame:
    df = pd.DataFrame(raw)
    df["year"] = df["year"].astype(int)
    df["week"] = df["week"].astype(int)
    df["date"] = df.apply(
        lambda r: epiweek_to_period_end(r["year"], r["week"]), axis=1
    )
    df["date"] = pd.to_datetime(df["date"], utc=True)

    # Resolve location. Use the `states` field; only keep state + national rows
    # (drop "NEW ENGLAND", "MIDDLE ATLANTIC", etc. — region rollups don't have a
    # standard FIPS code and are derivable from state rows downstream).
    state_upper = df["states"].fillna("").str.upper().str.strip()
    df["location_id"] = state_upper.map(STATE_NAME_TO_FIPS)
    df.loc[state_upper.isin(NATIONAL_NAMES), "location_id"] = "US"
    df = df.dropna(subset=["location_id"]).copy()

    # NYC special-case (synthetic FIPS) — fold into NY 36 (we lose the NYC carve-out;
    # acceptable for v0.1 since most sources don't separate NYC out).
    df.loc[df["location_id"] == "36-NYC", "location_id"] = "36"

    df["location_level"] = df["location_id"].apply(
        lambda x: "national" if x == "US" else "subnational-state"
    ).astype("category")
    df["location_name"] = df["states"]

    mapped = df["label"].apply(map_label)
    df["condition"] = mapped.apply(lambda t: t[0])
    df["condition_type"] = mapped.apply(lambda t: t[1]).astype("category")
    df["condition_native"] = df["label"]

    df["count"] = pd.to_numeric(df["m2"], errors="coerce")
    df["m2_flag"] = df["m2_flag"].astype(str)

    keep = ["date", "location_id", "location_level", "location_name",
            "condition", "condition_type", "condition_native", "count", "m2_flag"]
    df = df[keep]
    df = df.sort_values(["date", "location_id", "condition"]).reset_index(drop=True)
    return df


def main() -> None:
    print(f"Fetching {ENDPOINT}")
    raw = fetch()
    print(f"\nTotal raw rows: {len(raw):,}")
    df = parse_normalize(raw)
    print(f"After normalization: {len(df):,} rows × {len(df.columns)} cols")
    print(f"  date range: {df['date'].min().date()} → {df['date'].max().date()}")
    print(f"  unique conditions (mapped): {df['condition'].nunique()}")
    print(f"  unique conditions (native): {df['condition_native'].nunique()}")

    out_dir = Path(__file__).parent / "data"
    out_dir.mkdir(exist_ok=True)
    out_path = out_dir / "cdc-nndss.parquet"
    df.to_parquet(out_path, index=False)
    print(f"Wrote {out_path} ({out_path.stat().st_size / 1024 / 1024:.2f} MB)")


if __name__ == "__main__":
    main()
