# Follow-ups

Open work captured so we don't lose it. Completed items pruned — look
at git history if you need the original write-ups.

## 1. Boundary loading — cold-load perf (continuation)

Already shipped: timing logs, per-country-set filter cache, error
surfacing through the renderer, and a real spinner. If the *cold*
load is still slow on the iso3166-2 admin-1 file (2.2 MB raw, 757 KB
gzipped), the next moves are:

1. Convert the admin-1 GeoJSON → TopoJSON (~3-5× smaller on disk; gzip
   makes it tiny on the wire). Same pattern as `usAtlas`. Vendor the
   converted file via mapshaper or topojson CLI.
2. Move the JSON parse off the main thread (Web Worker). Bigger lift,
   only worth it if (1) isn't enough.

## 2. Stratified sampling for large datasets

`getDatasetSlice` caps fetches at `MAX_ROWS` (10,000) and pulls rows in
parquet order — `(date, location_id)` ascending. For datasets larger
than the cap (`nyt-covid` 2.5M, `jhu-csse-covid` 225k, `rsv-forecast-hub`
462k, `global-mobility` 11.7M, `owid-covid` 397k, `owid-mpox` 154k,
`flu-metrocast-hub` 132k), the user only sees the *earliest* rows.

The 10k bump fixes everything under that size. For the big sources
the right answer is stratified sampling: fetch K chunks of `MAX_ROWS / K`
rows each at evenly-spaced offsets across `[0, total)`. Same total
fetch volume, temporally representative slice.

Implementation sketch:

- New `getStratifiedDatasetSlice` in `src/data/hf/rows.ts` — picks
  K offsets, fetches `MAX_ROWS / K` rows at each.
- Switch `useDatasetSlice` to call the stratified version when
  `total > MAX_ROWS`, sequential path when `total ≤ MAX_ROWS`.
- Update the truncation indicator to distinguish "first 10,000 of N"
  from "10,000 sampled across N".

Mostly in `rows.ts`; consumers don't change.

## 3. Seasonal chart — deferred polish

v1 of the year-over-year overlay is shipped. Items deferred from the
original plan:

- **Per-source `default_period` in card metadata.** So e.g. NHSN HRD
  defaults to flu-season-northern instead of calendar-year. New
  optional field in `card.yaml`; reader picks it up; UI uses as default.
- **Split-by in seasonal mode.** Currently shows a small "Split-by
  ignored in seasonal mode" badge and proceeds without it. Real story:
  N split-keys × M periods → potentially explosive line count. Wire
  through with a warning when the product exceeds ~20.
- **Partial-period annotation.** Lines that stop mid-period (the
  in-progress current period, or pre-coverage years) get a small
  "thru-W14 / partial" badge so the user knows it's incomplete, not
  abnormally low.
- **Period-over-period Δ overlay.** Each line shows the difference
  from the prior period. Useful but a separate mode toggle.
- **Custom-period definition UI.** Power-user feature; let users
  define "summer 2024" or arbitrary windows.

## Other (longer-horizon)

- Auto-ingest and update features (cron-driven re-ingests of live sources).
- Time-series aggregate-on-year/month/week features (downsampling toggles
  for the time-series chart).
- SARIMA, ARIMA, DL-Flusight features. Baseline predictions at any given
  timestamp.
- TAB / browser keyboard nav.
- Add datasets-of-predictions, calculate loss vs. truth, leaderboard.
- Crowdsource predictions from people on models? HF dataset of predictions?
- Allow local use of this tool without fetching from HF (offline mode).
