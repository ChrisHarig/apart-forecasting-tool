"""Canada FluWatch+ / Respiratory Virus Detection Surveillance — weekly.

The Public Health Agency of Canada publishes a single CSV with weekly tests
and detections by province, virus, and week. Long-format with a `virus`
dimension; we map `virus` to the row-level `condition` field.

Source: https://health-infobase.canada.ca/respiratory-virus-surveillance/
File:   RVD_WeeklyData.csv
Cadence: weekly
Geography: Canada national + 10 provinces / 3 territories (some grouped into "Prairies"/"Atlantic")
History: 2014 onward (varies by virus)
"""
from __future__ import annotations

from io import StringIO
from pathlib import Path

import pandas as pd
import requests

CSV_URL = (
    "https://health-infobase.canada.ca/src/data/respiratory-virus-detections/"
    "RVD_WeeklyData.csv"
)

# Canadian province name → ISO 3166-2.
PROVINCE_TO_ISO: dict[str, tuple[str, str]] = {
    "Canada": ("CA", "national"),
    "Alberta": ("CA-AB", "subnational-state"),
    "British Columbia": ("CA-BC", "subnational-state"),
    "Manitoba": ("CA-MB", "subnational-state"),
    "New Brunswick": ("CA-NB", "subnational-state"),
    "Newfoundland and Labrador": ("CA-NL", "subnational-state"),
    "Nova Scotia": ("CA-NS", "subnational-state"),
    "Ontario": ("CA-ON", "subnational-state"),
    "Prince Edward Island": ("CA-PE", "subnational-state"),
    "Quebec": ("CA-QC", "subnational-state"),
    "Québec": ("CA-QC", "subnational-state"),
    "Saskatchewan": ("CA-SK", "subnational-state"),
    "Yukon": ("CA-YT", "subnational-state"),
    "Northwest Territories": ("CA-NT", "subnational-state"),
    "Nunavut": ("CA-NU", "subnational-state"),
}

# Region rollups (Prairies / Atlantic / etc.) — mapped to synthetic codes.
REGION_TO_ISO: dict[str, tuple[str, str]] = {
    "Prairies": ("CA-PHAC-PRAIRIES", "subnational-region"),
    "Atlantic": ("CA-PHAC-ATLANTIC", "subnational-region"),
    "Territories": ("CA-PHAC-TERRITORIES", "subnational-region"),
}

# Source virus name → (condition slug, condition_type).
VIRUS_TO_CONDITION: dict[str, tuple[str, str]] = {
    "SARS-CoV-2":       ("sars-cov-2",            "pathogen"),
    "Influenza A":      ("influenza-a",           "pathogen"),
    "Influenza B":      ("influenza-b",           "pathogen"),
    "Influenza":        ("influenza",             "pathogen"),
    "RSV":              ("rsv",                   "pathogen"),
    "HMPV":             ("hmpv",                  "pathogen"),
    "ADV":              ("adenovirus",            "pathogen"),
    "HPIV":             ("parainfluenza",         "pathogen"),
    "EV/RV":            ("rhinovirus-enterovirus", "pathogen"),
    "HCoV":             ("seasonal-coronavirus",  "pathogen"),
}


def fetch() -> pd.DataFrame:
    print(f"Downloading {CSV_URL}")
    resp = requests.get(CSV_URL, timeout=120)
    resp.raise_for_status()
    return pd.read_csv(StringIO(resp.text))


def parse_normalize(raw: pd.DataFrame) -> pd.DataFrame:
    df = raw.copy()
    df["date"] = pd.to_datetime(df["date"], utc=True, errors="raise")

    # Province-level rows when `province` is a real province; otherwise use `region` rollup.
    is_province = df["province"].isin(PROVINCE_TO_ISO)
    df_prov = df[is_province].copy()
    df_reg = df[~is_province].copy()

    df_prov[["location_id", "location_level"]] = (
        df_prov["province"].map(PROVINCE_TO_ISO).apply(pd.Series)
    )
    df_prov["location_name"] = df_prov["province"]

    df_reg[["location_id", "location_level"]] = (
        df_reg["region"].map(REGION_TO_ISO).apply(pd.Series)
    )
    df_reg["location_name"] = df_reg["region"]

    df = pd.concat([df_prov, df_reg], ignore_index=True)
    df = df.dropna(subset=["location_id"]).copy()
    df["location_level"] = df["location_level"].astype("category")

    virus_resolved = df["virus"].map(VIRUS_TO_CONDITION)
    df["condition"] = virus_resolved.map(lambda t: t[0] if isinstance(t, tuple) else None)
    df["condition_type"] = virus_resolved.map(lambda t: t[1] if isinstance(t, tuple) else None)
    df = df.dropna(subset=["condition"]).copy()
    df["condition_type"] = df["condition_type"].astype("category")
    df = df.rename(columns={"virus": "condition_native"})

    df["tests"] = pd.to_numeric(df["tests"], errors="coerce")
    df["detections"] = pd.to_numeric(df["detections"], errors="coerce")
    df["percentpositive"] = pd.to_numeric(df["percentpositive"], errors="coerce")

    keep = ["date", "location_id", "location_level", "location_name",
            "condition", "condition_type", "condition_native",
            "tests", "detections", "percentpositive"]
    df = df[keep].copy()
    df = df.sort_values(["date", "location_id", "condition"]).reset_index(drop=True)
    return df


def main() -> None:
    raw = fetch()
    print(f"Raw rows: {len(raw):,}")
    df = parse_normalize(raw)
    print(f"After normalization: {len(df):,} rows × {len(df.columns)} cols")
    print(f"  date range: {df['date'].min().date()} → {df['date'].max().date()}")
    print(f"  conditions: {sorted(df['condition'].unique().tolist())}")
    print(f"  locations: {df['location_id'].nunique()}")

    out_dir = Path(__file__).parent / "data"
    out_dir.mkdir(exist_ok=True)
    out_path = out_dir / "canada-fluwatch.parquet"
    df.to_parquet(out_path, index=False)
    print(f"Wrote {out_path} ({out_path.stat().st_size / 1024:.1f} KB)")


if __name__ == "__main__":
    main()
