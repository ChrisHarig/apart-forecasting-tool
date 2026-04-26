"""JHU CSSE COVID-19 — global confirmed/deaths/recovered daily.

Three sibling CSVs (`confirmed_global`, `deaths_global`, `recovered_global`)
in wide-format (one column per date). We melt each into long, merge on
(country, province, date), and pivot the metric into wide value columns.

Source: https://github.com/CSSEGISandData/COVID-19
Cadence: daily (until 2023-03 archive)
Geography: country / province (mixed)
History: 2020-01-22 → 2023-03-09 (archived)
"""
from __future__ import annotations

from io import StringIO
from pathlib import Path

import pandas as pd
import requests

BASE = (
    "https://raw.githubusercontent.com/CSSEGISandData/COVID-19/master/"
    "csse_covid_19_data/csse_covid_19_time_series"
)
FILES = {
    "confirmed": f"{BASE}/time_series_covid19_confirmed_global.csv",
    "deaths":    f"{BASE}/time_series_covid19_deaths_global.csv",
    "recovered": f"{BASE}/time_series_covid19_recovered_global.csv",
}


def fetch_one(url: str) -> pd.DataFrame:
    print(f"  {url}")
    resp = requests.get(url, timeout=180)
    resp.raise_for_status()
    return pd.read_csv(StringIO(resp.text))


def melt_one(df: pd.DataFrame, value_name: str) -> pd.DataFrame:
    id_cols = ["Province/State", "Country/Region", "Lat", "Long"]
    melted = df.melt(id_vars=id_cols, var_name="date", value_name=value_name)
    melted["date"] = pd.to_datetime(melted["date"], format="%m/%d/%y", utc=True)
    return melted


def parse_normalize(frames: dict[str, pd.DataFrame]) -> pd.DataFrame:
    melted = {k: melt_one(v, k) for k, v in frames.items()}
    df = melted["confirmed"].merge(
        melted["deaths"], on=["Province/State", "Country/Region", "Lat", "Long", "date"],
        how="outer",
    ).merge(
        melted["recovered"], on=["Province/State", "Country/Region", "Lat", "Long", "date"],
        how="outer",
    )

    # Country-level: rows where Province/State is NaN. Province-level otherwise.
    # The province column carries names, not ISO 3166-2 codes — and many countries
    # use it for cruise ships / unconventional regions. We keep only national rolls
    # for v0.1; province-level rolls would need a country-by-country crosswalk.
    df_national = df[df["Province/State"].isna()].copy()

    import pycountry
    def cname_to_iso2(n: str) -> str | None:
        # Manual fixups for JHU's idiosyncratic names.
        manual = {
            "US": "US", "Korea, South": "KR", "Korea, North": "KP",
            "Taiwan*": "TW", "Burma": "MM", "Cabo Verde": "CV",
            "Congo (Brazzaville)": "CG", "Congo (Kinshasa)": "CD",
            "Cote d'Ivoire": "CI", "Czechia": "CZ",
            "Holy See": "VA", "Iran": "IR", "Laos": "LA",
            "Russia": "RU", "Syria": "SY", "Tanzania": "TZ",
            "Vietnam": "VN", "Brunei": "BN", "Bolivia": "BO",
            "Moldova": "MD", "West Bank and Gaza": "PS",
            "Kosovo": "XK", "Micronesia": "FM",
        }
        if n in manual:
            return manual[n]
        try:
            c = pycountry.countries.lookup(n)
            return c.alpha_2
        except LookupError:
            return None

    df_national["location_id"] = df_national["Country/Region"].apply(cname_to_iso2)
    unmapped = df_national[df_national["location_id"].isna()]["Country/Region"].unique()
    if len(unmapped):
        print(f"  WARN unmapped country names dropped: {sorted(unmapped.tolist())}")
        df_national = df_national.dropna(subset=["location_id"]).copy()

    df_national["location_level"] = pd.Categorical(
        ["national"] * len(df_national), categories=["national"]
    )
    df_national = df_national.rename(columns={"Country/Region": "location_name"})

    keep = ["date", "location_id", "location_level", "location_name",
            "confirmed", "deaths", "recovered"]
    df_national = df_national[keep].copy()
    df_national = df_national.sort_values(["date", "location_id"]).reset_index(drop=True)
    return df_national


def main() -> None:
    print("Downloading JHU CSSE COVID-19 time series:")
    frames = {k: fetch_one(u) for k, u in FILES.items()}
    df = parse_normalize(frames)
    print(f"After normalization: {len(df):,} rows × {len(df.columns)} cols")
    print(f"  date range: {df['date'].min().date()} → {df['date'].max().date()}")
    print(f"  countries: {df['location_id'].nunique()}")

    out_dir = Path(__file__).parent / "data"
    out_dir.mkdir(exist_ok=True)
    out_path = out_dir / "jhu-csse-covid.parquet"
    df.to_parquet(out_path, index=False)
    print(f"Wrote {out_path} ({out_path.stat().st_size / 1024 / 1024:.2f} MB)")


if __name__ == "__main__":
    main()
