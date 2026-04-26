"""CDC US Dengue — annual locally-acquired + travel-associated cases by jurisdiction.

CDC publishes annual dengue summaries on its dengue surveillance pages. There
isn't a stable CSV download; a small JSON file is embedded on the page. As a
v0.1 placeholder we declare the source and ingest the most recent year via a
manual snapshot. Full historical ingest is a TODO that should grow alongside
NNDSS dengue rows.

Source: https://www.cdc.gov/dengue/data-research/facts-stats/current-data.html
Cadence: weekly (per-jurisdiction reporting; CDC publishes monthly summaries)
Geography: US states + territories
History: varies; territories (PR/USVI/Guam/AS) have the longest series
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd

# Manual snapshot — pulled from the CDC dashboard 2026-04. The data is small
# enough (~50 jurisdiction-years) to inline; should be replaced by a live
# scrape if the dashboard exposes JSON in the future. This is the most
# fragile source in the batch and a candidate to drop in v0.2 if NNDSS
# coverage of dengue (already long-format-ingested) suffices.
SNAPSHOT_ROWS: list[dict] = [
    # Format: {"date": "...", "location_postal": "...", "locally_acquired": int, "travel_associated": int}
    # Intentionally empty for v0.1; populate from the CDC page on next run.
]


def main() -> None:
    print(
        "STUB — CDC dengue page does not expose a stable machine-readable feed.\n"
        "NNDSS (`cdc-nndss`) covers dengue cases via its arboviral labels;\n"
        "consider that the canonical source until CDC publishes an API."
    )
    out_dir = Path(__file__).parent / "data"
    out_dir.mkdir(exist_ok=True)
    pd.DataFrame(
        columns=["date", "location_id", "location_level", "location_name",
                 "locally_acquired", "travel_associated"]
    ).to_parquet(out_dir / "cdc-dengue-us.parquet", index=False)


if __name__ == "__main__":
    main()
