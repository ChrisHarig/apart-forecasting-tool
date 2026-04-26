"""ECDC ERVISS — ILI/ARI primary-care consultation rates ingest module.

Pulls `data/ILIARIRates.csv` from EU-ECDC/Respiratory_viruses_weekly_data on
GitHub. ERVISS publishes the file in long format with one row per (week,
country, indicator, age). We pivot the `indicator` axis into wide value
columns (`ili_rate`, `ari_rate`) and keep `age` as a row-level dimension so
filtering by age band is preserved.

Source: https://github.com/EU-ECDC/Respiratory_viruses_weekly_data
Cadence: weekly (ISO week, period-end Sunday)
Geography: EU/EEA national reports (28 reporting in current snapshot)
History: 2021-W25 onward
"""
from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone
from io import StringIO
from pathlib import Path

import pandas as pd
import requests

CSV_URL = (
    "https://raw.githubusercontent.com/"
    "EU-ECDC/Respiratory_viruses_weekly_data/main/data/ILIARIRates.csv"
)

# 30 EU/EEA national mappings. ECDC publishes English country names; we
# normalize to ISO 3166-1 alpha-2 for `location_id`. Note: Greece is "GR"
# in ISO (ECDC's internal "EL" code is not used in this CSV).
COUNTRY_NAME_TO_ISO2: dict[str, str] = {
    "Austria": "AT", "Belgium": "BE", "Bulgaria": "BG", "Croatia": "HR",
    "Cyprus": "CY", "Czechia": "CZ", "Denmark": "DK", "Estonia": "EE",
    "Finland": "FI", "France": "FR", "Germany": "DE", "Greece": "GR",
    "Hungary": "HU", "Iceland": "IS", "Ireland": "IE", "Italy": "IT",
    "Latvia": "LV", "Liechtenstein": "LI", "Lithuania": "LT", "Luxembourg": "LU",
    "Malta": "MT", "Netherlands": "NL", "Norway": "NO", "Poland": "PL",
    "Portugal": "PT", "Romania": "RO", "Slovakia": "SK", "Slovenia": "SI",
    "Spain": "ES", "Sweden": "SE",
}

INDICATOR_TO_VALUE_COL: dict[str, str] = {
    "ILIconsultationrate": "ili_rate",
    "ARIconsultationrate": "ari_rate",
}


def isoweek_to_period_end(yearweek: str) -> datetime:
    """ISO yearweek 'YYYY-Www' → period-end Sunday at UTC midnight."""
    year_str, week_str = yearweek.split("-W")
    monday = date.fromisocalendar(int(year_str), int(week_str), 1)
    sunday = monday + timedelta(days=6)
    return datetime.combine(sunday, time.min, tzinfo=timezone.utc)


def fetch() -> pd.DataFrame:
    print(f"Downloading {CSV_URL}")
    resp = requests.get(CSV_URL, timeout=120)
    resp.raise_for_status()
    return pd.read_csv(StringIO(resp.text))


def parse_normalize(raw: pd.DataFrame) -> pd.DataFrame:
    df = raw.copy()

    # Pivot indicator → wide. Keep `age` as a dimension so per-age series
    # remain intact for the dashboard (filter to `total` for headline series).
    pivoted = df.pivot_table(
        index=["countryname", "yearweek", "age"],
        columns="indicator",
        values="value",
        aggfunc="first",
    ).reset_index()
    pivoted.columns.name = None
    pivoted = pivoted.rename(columns=INDICATOR_TO_VALUE_COL)

    # Country name → ISO 3166-1 alpha-2.
    unmapped = sorted(set(pivoted["countryname"]) - set(COUNTRY_NAME_TO_ISO2))
    if unmapped:
        raise ValueError(
            f"Unmapped country names (extend COUNTRY_NAME_TO_ISO2): {unmapped}"
        )
    pivoted["location_id"] = pivoted["countryname"].map(COUNTRY_NAME_TO_ISO2)
    pivoted["location_level"] = pd.Categorical(
        ["national"] * len(pivoted), categories=["national"]
    )
    pivoted = pivoted.rename(columns={"countryname": "location_name"})

    # ISO yearweek → date (period-end Sunday, UTC).
    pivoted["date"] = pivoted["yearweek"].apply(isoweek_to_period_end)
    pivoted["date"] = pd.to_datetime(pivoted["date"], utc=True)
    pivoted = pivoted.drop(columns=["yearweek"])

    # Numeric coerce.
    for col in INDICATOR_TO_VALUE_COL.values():
        if col in pivoted.columns:
            pivoted[col] = pd.to_numeric(pivoted[col], errors="coerce")

    keep = ["date", "location_id", "location_level", "location_name", "age"]
    keep.extend(c for c in INDICATOR_TO_VALUE_COL.values() if c in pivoted.columns)
    pivoted = pivoted[keep].copy()

    pivoted = pivoted.sort_values(["date", "location_id", "age"]).reset_index(drop=True)
    return pivoted


def main() -> None:
    raw = fetch()
    print(f"Raw rows: {len(raw):,}")

    df = parse_normalize(raw)
    print(f"After normalization: {len(df):,} rows × {len(df.columns)} columns")
    print(f"  date range: {df['date'].min().date()} → {df['date'].max().date()}")
    print(f"  countries: {df['location_id'].nunique()}")
    print(f"  ages: {sorted(df['age'].unique())}")
    print()
    print("Sample rows (recent total-age):")
    sample = df[df["age"] == "total"].tail(3)
    print(sample.to_string(index=False))

    out_dir = Path(__file__).parent / "data"
    out_dir.mkdir(exist_ok=True)
    out_path = out_dir / "ecdc-erviss.parquet"
    df.to_parquet(out_path, index=False)
    print(f"\nWrote {out_path} ({out_path.stat().st_size / 1024:.1f} KB)")


if __name__ == "__main__":
    main()
