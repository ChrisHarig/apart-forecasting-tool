"""PAHO Dengue (Americas) — STUB.

The PAHO Arbo Portal exposes weekly dengue case counts for the Americas region
through a Shiny dashboard backed by an internal JSON endpoint. As of 2026-04
the PAHO infrastructure has been intermittent (502 errors); pin a working
endpoint before relying on this for live ingest.

Closest stable alternative: OpenDengue (`opendengue` source) covers PAHO
member countries via figshare archive; PAHO's live weekly view should remain
its own source for currency.

Source: https://www.paho.org/en/arbo-portal/dengue-data-and-analysis
Cadence: weekly
Geography: 46 countries / territories of the Americas
History: 1980+ (annual via GHO; weekly portal varies)
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd

# PLACEHOLDER endpoint — PAHO Arbo Portal AJAX path is currently 502;
# verify and replace before relying on this ingest in production.
ENDPOINT_PLACEHOLDER = "https://ais.paho.org/phip/viz/ed_dengue_cases.json"


def main() -> None:
    print(
        "STUB — PAHO Arbo Portal endpoint returned 502 during pipeline build (2026-04-26).\n"
        "Re-verify the AJAX/JSON endpoint backing the Shiny app before live ingest.\n"
        "For static historical coverage, prefer the `opendengue` source which already\n"
        "covers PAHO member countries through 2023."
    )
    out_dir = Path(__file__).parent / "data"
    out_dir.mkdir(exist_ok=True)
    pd.DataFrame(
        columns=["date", "location_id", "location_level", "location_name", "cases"]
    ).to_parquet(out_dir / "paho-dengue.parquet", index=False)


if __name__ == "__main__":
    main()
