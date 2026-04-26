"""OpenDengue — national-level dengue case counts ingest module.

Pulls the V1.3 National extract from OpenDengue/master-repo on GitHub. The file
is a long-format archive with one row per (country × calendar period × case
definition); a single (country, date) cell can have multiple rows when the
source distinguishes case definitions (Suspected vs Confirmed vs Probable etc.).

OpenDengue is a static archive. Reproduce by re-running this module against the
pinned RELEASE_TAG; future versions of OpenDengue will require bumping that tag.

Source: https://opendengue.org/
GitHub: https://github.com/OpenDengue/master-repo
Cadence: irregular (some countries report weekly, others monthly)
Geography: 129 countries (national)
History: 1924 onward (per-country availability varies)
"""
from __future__ import annotations

import io
import zipfile
from datetime import datetime, time, timezone
from pathlib import Path

import pandas as pd
import pycountry
import requests

RELEASE_TAG = "V1.3"
EXTRACT_URL = (
    f"https://github.com/OpenDengue/master-repo/raw/main/data/releases/"
    f"{RELEASE_TAG}/National_extract_V1_3.zip"
)
CSV_NAME_IN_ZIP = "National_extract_V1_3.csv"

# Columns we keep (others — adm_1_name, adm_2_name, IBGE_code, FAO_GAUL_code,
# RNE_iso_code, full_name, Year, UUID — are dropped: full_name duplicates
# adm_0_name, sub-national fields are NaN at the national grain, GAUL/IBGE/RNE
# are alternate location encodings, Year is redundant with calendar_end_date,
# UUID is upstream provenance).
SOURCE_COLUMNS = [
    "adm_0_name",
    "ISO_A0",
    "calendar_start_date",
    "calendar_end_date",
    "dengue_total",
    "case_definition_standardised",
    "T_res",
]

# Per-country temporal cadences vary; we keep the row-level temporal_resolution
# column and drop coarse aggregates (Year, Total) so the dataset is series-shaped.
KEPT_TEMPORAL_RES = {"Week", "Month"}


def fetch_csv() -> pd.DataFrame:
    print(f"Downloading {EXTRACT_URL}")
    resp = requests.get(EXTRACT_URL, timeout=180)
    resp.raise_for_status()
    with zipfile.ZipFile(io.BytesIO(resp.content)) as zf:
        with zf.open(CSV_NAME_IN_ZIP) as f:
            return pd.read_csv(f)


def iso3_to_iso2(code: str) -> str | None:
    if not isinstance(code, str) or len(code) != 3:
        return None
    country = pycountry.countries.get(alpha_3=code)
    return country.alpha_2 if country else None


def parse_normalize(raw: pd.DataFrame) -> pd.DataFrame:
    df = raw[SOURCE_COLUMNS].copy()

    # Drop coarse temporal aggregates — they don't form a time series.
    df = df[df["T_res"].isin(KEPT_TEMPORAL_RES)].copy()

    # ISO3 → ISO2. OpenDengue uses ISO 3166-1 alpha-3 in ISO_A0; we normalize
    # to alpha-2 to match the EPI-Eval national location_id convention.
    df["location_id"] = df["ISO_A0"].apply(iso3_to_iso2)
    unmapped = df[df["location_id"].isna()]["ISO_A0"].dropna().unique()
    if len(unmapped) > 0:
        raise ValueError(
            f"ISO3 codes that could not be mapped to ISO2 via pycountry: "
            f"{sorted(unmapped.tolist())}"
        )
    df["location_level"] = pd.Categorical(
        ["national"] * len(df), categories=["national"]
    )

    # calendar_end_date → date (period-end, UTC midnight).
    df["date"] = pd.to_datetime(df["calendar_end_date"], utc=True)
    df = df.dropna(subset=["date"])

    df = df.rename(
        columns={
            "adm_0_name": "location_name",
            "case_definition_standardised": "case_definition",
            "T_res": "temporal_resolution",
        }
    )
    # Source has both "Confirmed" and "confirmed" — collapse to one canonical form
    # so the dashboard filter doesn't show duplicate options.
    df["case_definition"] = df["case_definition"].str.replace(
        r"^confirmed$", "Confirmed", regex=True
    )
    df["dengue_total"] = pd.to_numeric(df["dengue_total"], errors="coerce")

    keep = [
        "date",
        "location_id",
        "location_level",
        "location_name",
        "case_definition",
        "temporal_resolution",
        "dengue_total",
    ]
    df = df[keep]

    df = df.sort_values(
        ["date", "location_id", "case_definition", "temporal_resolution"]
    ).reset_index(drop=True)
    return df


def main() -> None:
    raw = fetch_csv()
    print(f"Raw rows: {len(raw):,}")

    df = parse_normalize(raw)
    print(f"After normalization: {len(df):,} rows × {len(df.columns)} columns")
    print(f"  date range: {df['date'].min().date()} → {df['date'].max().date()}")
    print(f"  countries: {df['location_id'].nunique()}")
    print(f"  case definitions: {sorted(df['case_definition'].unique())}")
    print(f"  temporal resolutions: {sorted(df['temporal_resolution'].unique())}")
    print()
    print("Sample rows (recent BR):")
    sample = df[df["location_id"] == "BR"].tail(3)
    print(sample.to_string(index=False))

    out_dir = Path(__file__).parent / "data"
    out_dir.mkdir(exist_ok=True)
    out_path = out_dir / "opendengue.parquet"
    df.to_parquet(out_path, index=False)
    print(f"\nWrote {out_path} ({out_path.stat().st_size / 1024:.1f} KB)")


if __name__ == "__main__":
    main()
