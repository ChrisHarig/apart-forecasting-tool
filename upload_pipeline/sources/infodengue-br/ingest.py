"""InfoDengue (Brazil) — STUB.

InfoDengue exposes per-municipality weekly dengue / chikungunya / zika nowcasts
through the Mosqlimate API. The endpoint requires an API key as of 2026-04.
Apply for one at https://api.mosqlimate.org/ and store under
`MOSQLIMATE_API_KEY` in `.env` before populating this ingest.

Source: https://api.mosqlimate.org/docs/datastore/GET/infodengue/
Cadence: weekly
Geography: ~5,570 Brazilian municipalities (IBGE 7-digit codes — schema falls
           back to BR-IBGE-XXXXXXX prefix for sub-state IDs).
History: 2015+ for dengue; chik/zika later.
"""
from __future__ import annotations

import os
from pathlib import Path

import pandas as pd
import requests

ENDPOINT = "https://api.mosqlimate.org/api/datastore/infodengue/"
API_KEY = os.getenv("MOSQLIMATE_API_KEY")


def fetch(disease: str = "dengue") -> list[dict]:
    if not API_KEY:
        raise RuntimeError(
            "MOSQLIMATE_API_KEY not set. Apply at https://api.mosqlimate.org/ "
            "and set the env var before running this ingest."
        )
    headers = {"X-UID-KEY": API_KEY}
    rows: list[dict] = []
    page = 1
    while True:
        resp = requests.get(
            ENDPOINT,
            headers=headers,
            params={"disease": disease, "page": page, "page_size": 1000},
            timeout=180,
        )
        resp.raise_for_status()
        payload = resp.json()
        items = payload.get("items", [])
        if not items:
            break
        rows.extend(items)
        page += 1
    return rows


def parse_normalize(raw: list[dict]) -> pd.DataFrame:
    df = pd.DataFrame(raw)
    if df.empty:
        return df
    # InfoDengue's `data_iniSE` is the ISO week start; we use period-end Sunday.
    df["date"] = pd.to_datetime(df["data_iniSE"], utc=True) + pd.Timedelta(days=6)
    df["location_id"] = "BR-IBGE-" + df["geocode"].astype(str)
    df["location_level"] = pd.Categorical(
        ["subnational-county"] * len(df), categories=["subnational-county"]
    )
    df["location_id_native"] = df["geocode"].astype(str)
    df["location_name"] = df.get("nome", df["geocode"]).astype(str)

    for col in ("casos", "casos_est", "p_rt1", "p_inc100k", "Rt"):
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    keep = ["date", "location_id", "location_level", "location_id_native",
            "location_name", "casos", "casos_est", "p_rt1", "p_inc100k", "Rt"]
    df = df[[c for c in keep if c in df.columns]].copy()
    df = df.sort_values(["date", "location_id"]).reset_index(drop=True)
    return df


def main() -> None:
    print(
        "STUB — Mosqlimate API requires X-UID-KEY auth. Set MOSQLIMATE_API_KEY env var.\n"
        "Apply at https://api.mosqlimate.org/."
    )
    out_dir = Path(__file__).parent / "data"
    out_dir.mkdir(exist_ok=True)
    pd.DataFrame(
        columns=["date", "location_id", "location_level", "location_id_native",
                 "location_name", "casos", "casos_est", "p_rt1", "p_inc100k", "Rt"]
    ).to_parquet(out_dir / "infodengue-br.parquet", index=False)


if __name__ == "__main__":
    main()
