"""OWID COVID-19 ingest.

Pulls Our World in Data's compiled global COVID-19 time series. Single CSV with
~100 columns covering cases, deaths, hospitalisations, vaccinations, testing,
mobility-style covariates, and demographic metadata. We retain the case/death/
hospital cluster (the time-varying *outcomes*) and a small set of structural
covariates (population, GDP) but drop the 70+ redundant smoothing/per-capita
variants — the dashboard can derive those on the fly.

Source: https://github.com/owid/covid-19-data
File:   public/data/owid-covid-data.csv
Cadence: daily, but with weekly publication for many countries (so observed
         spacing per location is highly mixed).
Geography: 219 countries + region aggregates (`World`, continents, income groups).
History: 2020-01 onward.
"""
from __future__ import annotations

from io import StringIO
from pathlib import Path

import pandas as pd
import requests

CSV_URL = (
    "https://raw.githubusercontent.com/owid/covid-19-data/master/"
    "public/data/owid-covid-data.csv"
)

# OWID's `iso_code` is mostly ISO 3166-1 alpha-3 plus synthetic codes for
# aggregations (OWID_WRL, OWID_AFR, OWID_EUN, OWID_HIC, ...). We keep ISO3
# countries as `national` rows and drop the OWID_* aggregates — they're
# derivable downstream from the country rows, and don't carry an ISO2.
KEEP_NON_ISO3 = {"OWID_WRL"}  # World aggregate is genuinely useful as a global row

VALUE_COLUMNS = [
    "new_cases",
    "new_deaths",
    "icu_patients",
    "hosp_patients",
    "weekly_icu_admissions",
    "weekly_hosp_admissions",
    "new_tests",
    "positive_rate",
    "people_vaccinated",
    "people_fully_vaccinated",
    "total_boosters",
]


def fetch() -> pd.DataFrame:
    print(f"Downloading {CSV_URL}")
    resp = requests.get(CSV_URL, timeout=180)
    resp.raise_for_status()
    return pd.read_csv(StringIO(resp.text), low_memory=False)


def iso3_to_iso2(code: str) -> str | None:
    import pycountry
    if not isinstance(code, str) or len(code) != 3:
        return None
    c = pycountry.countries.get(alpha_3=code)
    return c.alpha_2 if c else None


def parse_normalize(raw: pd.DataFrame) -> pd.DataFrame:
    df = raw.copy()

    # Resolve location_id. Real ISO3 → ISO2 national; OWID_WRL → "WORLD" (global level).
    df["location_id"] = df["iso_code"].apply(iso3_to_iso2)
    is_world = df["iso_code"] == "OWID_WRL"
    df.loc[is_world, "location_id"] = "WORLD"

    df["location_level"] = pd.Series(["national"] * len(df), dtype="object")
    df.loc[is_world, "location_level"] = "global"

    # Drop OWID synthetic aggregates other than world (continents, income groups).
    keep_mask = df["location_id"].notna()
    keep_mask |= df["iso_code"].isin(KEEP_NON_ISO3)
    df = df[keep_mask].copy()

    df = df.rename(columns={"location": "location_name"})
    df["date"] = pd.to_datetime(df["date"], utc=True, errors="raise")
    df["location_level"] = df["location_level"].astype("category")

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
    print(f"Raw rows: {len(raw):,}, cols: {len(raw.columns)}")

    df = parse_normalize(raw)
    print(f"After normalization: {len(df):,} rows × {len(df.columns)} cols")
    print(f"  date range: {df['date'].min().date()} → {df['date'].max().date()}")
    print(f"  unique locations: {df['location_id'].nunique()}")

    out_dir = Path(__file__).parent / "data"
    out_dir.mkdir(exist_ok=True)
    out_path = out_dir / "owid-covid.parquet"
    df.to_parquet(out_path, index=False)
    print(f"Wrote {out_path} ({out_path.stat().st_size / 1024 / 1024:.2f} MB)")


if __name__ == "__main__":
    main()
