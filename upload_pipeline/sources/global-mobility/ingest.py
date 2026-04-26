"""Google Community Mobility Reports — global daily, multi-resolution.

Pulls the canonical Global_Mobility_Report.csv (~1.1 GB) from Google's CDN,
melts the multi-resolution geography stack (country / state / county / metro /
place_id) into single `location_id` + `location_level` columns, and renames
the verbose `*_percent_change_from_baseline` columns to short forms.

Source: https://www.google.com/covid19/mobility/
File:   https://www.gstatic.com/covid19/mobility/Global_Mobility_Report.csv
Cadence: daily (data collection ended 2022-10-15, file remains static)
Geography: 200+ countries; states; US counties; metros
History: 2020-02-15 → 2022-10-15

The schema's geography rules pick the most-specific populated field per row:
  - county FIPS present  → subnational-county
  - ISO 3166-2 present   → subnational-state
  - metro_area present   → subnational-city  (synthetic `<ISO2>-METRO-<id>`)
  - country code only    → national
"""
from __future__ import annotations

import io
from pathlib import Path

import pandas as pd
import requests

CSV_URL = "https://www.gstatic.com/covid19/mobility/Global_Mobility_Report.csv"

VALUE_COL_RENAMES = {
    "retail_and_recreation_percent_change_from_baseline": "retail_and_recreation",
    "grocery_and_pharmacy_percent_change_from_baseline":  "grocery_and_pharmacy",
    "parks_percent_change_from_baseline":                 "parks",
    "transit_stations_percent_change_from_baseline":      "transit_stations",
    "workplaces_percent_change_from_baseline":            "workplaces",
    "residential_percent_change_from_baseline":           "residential",
}
VALUE_COLUMNS = list(VALUE_COL_RENAMES.values())


def fetch() -> pd.DataFrame:
    print(f"Downloading {CSV_URL}  (~1.1 GB)")
    resp = requests.get(CSV_URL, timeout=600, stream=True)
    resp.raise_for_status()
    # Stream to memory then read; pandas needs the full bytes for read_csv.
    buf = io.BytesIO()
    bytes_read = 0
    for chunk in resp.iter_content(chunk_size=1024 * 1024):
        buf.write(chunk)
        bytes_read += len(chunk)
        if bytes_read % (50 * 1024 * 1024) < (1024 * 1024):
            print(f"  {bytes_read / 1024 / 1024:.0f} MB")
    buf.seek(0)
    return pd.read_csv(buf, low_memory=False, dtype={
        "country_region_code": str,
        "iso_3166_2_code": str,
        "census_fips_code": str,
        "metro_area": str,
        "place_id": str,
    })


def _resolve_location(row: pd.Series) -> tuple[str | None, str | None]:
    """Pick the most-specific populated geography for this row."""
    fips = row.get("census_fips_code")
    iso_2 = row.get("iso_3166_2_code")
    metro = row.get("metro_area")
    cc = row.get("country_region_code")

    if isinstance(fips, str) and fips:
        # County FIPS is published as a 4- or 5-digit string; pad to 5.
        fips_padded = fips.split(".")[0].zfill(5)
        if len(fips_padded) == 5 and fips_padded.isdigit():
            return fips_padded, "subnational-county"
    if isinstance(iso_2, str) and iso_2:
        return iso_2, "subnational-state"
    if isinstance(metro, str) and metro and isinstance(cc, str) and cc:
        # No standard ID for metros — synthesise from country + slugified name.
        slug = "".join(ch if ch.isalnum() else "-" for ch in metro).strip("-").upper()
        return f"{cc.upper()}-METRO-{slug}", "subnational-city"
    if isinstance(cc, str) and len(cc) == 2:
        return cc.upper(), "national"
    return None, None


def parse_normalize(raw: pd.DataFrame) -> pd.DataFrame:
    df = raw.copy()
    df["date"] = pd.to_datetime(df["date"], utc=True, errors="raise")

    print("Resolving geography per row ...")
    resolved = df.apply(_resolve_location, axis=1, result_type="expand")
    df["location_id"] = resolved[0]
    df["location_level"] = resolved[1]
    n_drop = int(df["location_id"].isna().sum())
    if n_drop:
        print(f"  dropping {n_drop:,} rows with no resolvable location")
    df = df.dropna(subset=["location_id"]).copy()
    df["location_level"] = df["location_level"].astype("category")

    # Build a human-readable name from the most-specific filled column.
    def _name(r: pd.Series) -> str:
        for k in ("sub_region_2", "metro_area", "sub_region_1", "country_region"):
            v = r.get(k)
            if isinstance(v, str) and v:
                return v
        return ""
    df["location_name"] = df.apply(_name, axis=1)

    df = df.rename(columns=VALUE_COL_RENAMES)
    for col in VALUE_COLUMNS:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    keep = ["date", "location_id", "location_level", "location_name", *VALUE_COLUMNS]
    df = df[keep].copy()
    df = df.sort_values(["date", "location_id"]).reset_index(drop=True)
    return df


def main() -> None:
    raw = fetch()
    print(f"Raw rows: {len(raw):,}")
    df = parse_normalize(raw)
    print(f"After normalization: {len(df):,} rows × {len(df.columns)} cols")
    print(f"  date range: {df['date'].min().date()} → {df['date'].max().date()}")
    print(f"  unique locations: {df['location_id'].nunique():,}")
    print(f"  level breakdown: {df['location_level'].value_counts().to_dict()}")

    out_dir = Path(__file__).parent / "data"
    out_dir.mkdir(exist_ok=True)
    out_path = out_dir / "global-mobility.parquet"
    df.to_parquet(out_path, index=False, compression="zstd")
    print(f"Wrote {out_path} ({out_path.stat().st_size / 1024 / 1024:.2f} MB)")


if __name__ == "__main__":
    main()
