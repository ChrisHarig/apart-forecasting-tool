# EPI-Eval

Frontend for browsing the [EPI-Eval](https://huggingface.co/EPI-Eval) collection
of curated epidemiological datasets. Source-first: pick a dataset, view it as
a timeline, on a map, or alongside related news.

## Layout

A multi-pane workspace (no sidebar nav). Four pane types:

- **Explorer** — dataset list + map of geographic coverage.
- **Graph** — scrollable timeline of any numeric field; per-row table view.
- **Map** — country / sub-state choropleth backed by MapLibre + world-atlas boundaries.
- **Feed** — news / activity stream tied to the active dataset(s).

Panes are arranged in a `WorkspaceGrid`; the active dataset selection is
shared across panes through `WorkspaceContext`.

## Run locally

```bash
npm install
npm run dev      # http://localhost:5173
npm test
npm run build
```

## Data

Datasets are pulled from [`EPI-Eval`](https://huggingface.co/EPI-Eval) on
HuggingFace. The ingest pipeline that publishes to that org lives under
[`upload_pipeline/`](upload_pipeline/) and is independent of the dashboard
runtime — see [`upload_pipeline/INGEST_BATCH_REPORT.md`](upload_pipeline/INGEST_BATCH_REPORT.md)
for the current dataset coverage.

## Predictions

Each truth dataset has an `EPI-Eval/<id>-predictions` companion repo on
HuggingFace that accumulates community-submitted forecasts in long format
(one row per quantile per target date). Two flows in the dashboard:

- **Submit** — drag a CSV onto a personal dataset, pick a target dataset
  to compare against, and click *Submit to HuggingFace*. The dashboard
  serializes your CSV to parquet and opens a community PR on the
  matching companion repo. Needs a free HF Write token, prompted inline.
- **View** — open any truth dataset and toggle the **Predictions** chip
  on the graph view. Accepted submissions overlay as dashed median lines
  with 80% interval bands per submitter; a leaderboard panel below the
  chart scores each submitter (MAE / WIS / rWIS vs naive / coverage)
  against the chart's current truth slice.

Companion repos are bootstrapped automatically when a new truth dataset
is uploaded. The pipeline scripts live alongside the ingest:
`upload_pipeline/core/{bootstrap,verify,seed_synth}_predictions_repos.py`.

## Deployment

GitHub Pages workflow at `.github/workflows/deploy.yml` runs `npm ci`,
`npm test`, `npm run build`, and publishes `dist/`.

## Engineering notes

See [`DEVELOPER_README.md`](DEVELOPER_README.md) for the longer engineering
handoff (component map, state shape, known limitations).
