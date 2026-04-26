# Sentinel Atlas

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

## Deployment

GitHub Pages workflow at `.github/workflows/deploy.yml` runs `npm ci`,
`npm test`, `npm run build`, and publishes `dist/`.

## Engineering notes

See [`DEVELOPER_README.md`](DEVELOPER_README.md) for the longer engineering
handoff (component map, state shape, known limitations).
