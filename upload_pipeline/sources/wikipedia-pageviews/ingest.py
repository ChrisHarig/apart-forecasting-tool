"""Wikipedia pageviews — daily views for selected disease-related articles.

Pulls daily English Wikipedia pageviews for a curated list of articles likely
to correlate with respiratory virus interest (`Influenza`, `COVID-19`, `RSV`,
`Common cold`, `Pneumonia`, ...). Each row is (date, article, views).

Source: https://wikimedia.org/api/rest_v1/metrics/pageviews/...
Cadence: daily
Geography: per-article (no geographic dimension; we use `WORLD` global level)
History: 2015-07 onward (REST API window)
"""
from __future__ import annotations

import time as _time
from datetime import date, datetime, timezone
from pathlib import Path

import pandas as pd
import requests

PROJECT = "en.wikipedia"
ACCESS = "all-access"
AGENT = "all-agents"

ARTICLES = [
    "Influenza", "COVID-19", "Respiratory_syncytial_virus",
    "Common_cold", "Pneumonia", "Mpox", "Measles", "Norovirus",
    "Dengue_fever", "Whooping_cough", "Ebola_virus_disease",
    "Tuberculosis",
]

START = "2015070100"
END   = datetime.now(timezone.utc).strftime("%Y%m%d") + "00"


def fetch_article(article: str) -> list[dict]:
    url = (
        f"https://wikimedia.org/api/rest_v1/metrics/pageviews/"
        f"per-article/{PROJECT}/{ACCESS}/{AGENT}/{article}/daily/{START}/{END}"
    )
    resp = requests.get(url, headers={"User-Agent": "epi-eval-pipeline/0.1"}, timeout=120)
    if resp.status_code == 404:
        return []
    resp.raise_for_status()
    return resp.json().get("items", [])


def parse_normalize(records: list[dict]) -> pd.DataFrame:
    df = pd.DataFrame(records)
    if df.empty:
        return df
    df["date"] = pd.to_datetime(df["timestamp"].str[:8], format="%Y%m%d", utc=True)
    df["location_id"] = "WORLD"
    df["location_level"] = pd.Categorical(["global"] * len(df), categories=["global"])
    df["location_name"] = "Wikipedia (en) global"
    df["views"] = pd.to_numeric(df["views"], errors="coerce")
    # `article` is the row-level segmentation value. Per schema, this is a
    # `topic` (a Wikipedia article isn't a clinical `condition`).
    df["topic"] = df["article"].astype(str)
    df["topic_type"] = pd.Categorical(["article"] * len(df), categories=["article"])

    keep = ["date", "location_id", "location_level", "location_name",
            "topic", "topic_type", "views"]
    df = df[keep].copy()
    df = df.sort_values(["date", "topic"]).reset_index(drop=True)
    return df


def main() -> None:
    records: list[dict] = []
    for art in ARTICLES:
        page = fetch_article(art)
        records.extend(page)
        print(f"  {art}: {len(page):,}")
        _time.sleep(0.5)

    df = parse_normalize(records)
    print(f"\nNormalized: {len(df):,} rows × {len(df.columns)} cols")
    if not df.empty:
        print(f"  date range: {df['date'].min().date()} → {df['date'].max().date()}")

    out_dir = Path(__file__).parent / "data"
    out_dir.mkdir(exist_ok=True)
    out_path = out_dir / "wikipedia-pageviews.parquet"
    df.to_parquet(out_path, index=False)
    print(f"Wrote {out_path} ({out_path.stat().st_size / 1024:.1f} KB)")


if __name__ == "__main__":
    main()
