# EPI-Eval Dashboard — Developer README

Last updated: 2026-04-25

The dashboard is a pure-frontend Vite app that browses and visualizes the EPI-Eval Huggingface org. There is no backend service in this repo — the upload pipeline (`upload_pipeline/`) pushes datasets to Huggingface, and the dashboard reads them back at runtime.

## Architecture in one breath

- `data/` and `upload_pipeline/` build the EPI-Eval Huggingface datasets.
- The dashboard treats Huggingface as the canonical store and fetches the catalog + per-dataset rows directly from the browser.
- Selected sources persist in `localStorage`. Catalog and per-dataset row pulls are cached in `localStorage` with a 1-hour TTL.

## Commands

```bash
npm install
npm run dev      # http://localhost:5173/
npm test
npm run build
npm run preview
```

## Stack

- Vite + React + TypeScript
- Tailwind CSS
- MapLibre GL JS + world-atlas + topojson-client (map view)
- Recharts (graph view)
- lucide-react (icons)
- Vitest

## App layout

```
src/App.tsx
src/main.tsx
src/state/DashboardContext.tsx     # view, selected/focused sources, catalog, rows
src/types/{source,dashboard,news}.ts
src/data/hf/                       # Huggingface client, cache, catalog, rows
src/components/Layout/DashboardShell.tsx
src/components/Navigation/SideNav.tsx
src/components/Feed/FeedPage.tsx
src/components/Sources/SourcesPage.tsx
src/components/Graph/GraphPage.tsx
src/components/Map/{MapPage,WorldMap,mapConfig,countrySelectionLayer}.tsx
src/components/News/NewsPage.tsx
```

The shell renders a left sidebar (app title, view nav, selected sources list, focused source pill) and a single main content area whose contents depend on the active view.

## Views

```ts
type DashboardView = "feed" | "sources" | "graph" | "map" | "news";
```

- **Feed** — landing view. Recently updated sources, news preview, your selected sources.
- **Sources** — catalog browser. Search, group by surveillance category, click to select.
- **Graph** — Recharts timeline of the focused source's first numeric value column. Metric and location pickers if the dataset has multiple.
- **Map** — MapLibre world map (zoom up to 20). Country click selects locally; not yet wired into the data layer.
- **News** — placeholder feed; renders an empty state until a feed adapter is connected.

## Huggingface data layer

`src/data/hf/`:

- `client.ts` — fetch wrappers for `https://huggingface.co/api/datasets?author=EPI-Eval&full=true` and `https://datasets-server.huggingface.co/rows`. Reads `import.meta.env.VITE_HF_TOKEN` if present.
- `cache.ts` — `localStorage` TTL cache (default 1h).
- `catalog.ts` — `getCatalog()` returns `SourceMetadata[]` parsed from each dataset's `cardData` (the YAML frontmatter from `upload_pipeline/schema/schema_v0.1.md`).
- `rows.ts` — `getDatasetSlice(datasetId, { max })` paginates the rows endpoint, capped at 5000 rows. Helpers `detectDateField` and `detectNumericFields` fall back to heuristics when the card metadata is missing.

The `SourceMetadata` shape in `src/types/source.ts` mirrors the curated keys from the EPI-Eval card schema (`surveillance_category`, `pathogens`, `value_columns`, `geography_levels`, `cadence`, `tier`, `computed.time_coverage`, etc.).

### Auth

Public EPI-Eval datasets work without auth. For private datasets, set `VITE_HF_TOKEN` in `.env` (Vite only exposes env vars prefixed with `VITE_`). The repo root `.env` already has `HF_TOKEN` for the upload pipeline; mirror it as `VITE_HF_TOKEN` if the dashboard needs it.

## State

`DashboardContext` exposes:

- `view` / `setView` (persisted to localStorage)
- `catalog` async state (loaded on mount, refreshable from Sources)
- `selectedSourceIds` (persisted to localStorage), `toggleSourceSelected`, `clearSelectedSources`
- `focusedSourceId` / `setFocusedSourceId`, `focusedSource` (resolved against catalog)
- `rows` async state for the focused source (auto-refetched when focus changes)
- `news` placeholder feed

## Testing

Vitest runs node-environment unit tests. Coverage focuses on the parts that have nontrivial logic:

- `src/data/hf/catalog.test.ts` — schema mapping
- `src/data/hf/cache.test.ts` — TTL semantics
- `src/data/hf/rows.test.ts` — date/numeric field detection

## Verification before handoff

```bash
npm test
npm run build
```

For UI changes, also start the dev server and check:

- The Sources view loads the EPI-Eval catalog from Huggingface.
- Adding a source updates the sidebar Selected list and persists across reload.
- The Graph view renders a timeline for the focused source and switches metric/location.
- The Map view zooms in to high detail.

## Removed surfaces

The previous version of this app had country-first navigation, a synthetic source catalog, an upload UI inside the dashboard, source validation, a coverage matrix, and a FastAPI backend scaffold. All have been removed. The data ingestion lives in `upload_pipeline/` and pushes to Huggingface; the dashboard never talks to a custom backend.
