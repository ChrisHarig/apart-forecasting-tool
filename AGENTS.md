# Agent guide

Notes for future agents working in this repo. Things that are easy to
break, conventions that aren't obvious from the code, and the few
non-trivial design decisions worth knowing about before changing things.
For an end-user-facing summary, see `DEVELOPER_README.md`. For known
follow-ups, see `FOLLOW_UPS.md`.

## What this is, in 30 seconds

A pure-frontend dashboard for the EPI-Eval Huggingface org
(`huggingface.co/EPI-Eval`). The catalog and per-dataset rows are fetched
**directly from Huggingface at runtime** — no backend service, no bundled
data. The dashboard is a workspace of up to four panes, each pane either
the dataset browser or an explorer (graph + map + table) for one
dataset.

Pipeline (Python, in `upload_pipeline/`) is the *write* side that pushes
datasets to Huggingface. The dashboard is the *read* side. They share no
runtime code — only the schema in `upload_pipeline/schema/schema_v0.1.md`.

## Things that are easy to break

These have actually broken at least once. Be careful when touching them.

1. **Charts must aggregate per timestamp by default.** Long-format sources
   (OpenDengue, NNDSS, anything with multiple rows per (date, location))
   produce a zigzag if you connect raw rows. The chart's default behavior
   is to bucket rows into `(groupKey, date)` and reduce with the column's
   declared `aggregation` (`pickAggregation` in
   `Graph/SourceTimelineChart.tsx`). Group-by *disaggregates* — it splits
   the default aggregate into multiple series — it doesn't aggregate.
2. **MapLibre `feature-state` for the chloropleth must be written even
   for missing features.** The scrubber writes a per-feature normalized
   value each tick. Skipping a feature leaves its previous color in
   place, so we explicitly write `-1` (the `NO_DATA` sentinel) for
   features absent from `valueByLocation`. See `Map/BoundaryMap.tsx`.
3. **Dual-handle range slider relies on pointer-events trickery.** Two
   `<input type="range">` overlay one bar; their `*-runnable-track` is
   `pointer-events: none` so the playhead's input below can capture
   clicks in the active band, while the thumbs themselves are
   `pointer-events: auto`. See `.dual-range-input` and `.playhead-range`
   in `styles/globals.css`. If clicks stop registering in the band or
   the trim handles disappear behind the playhead, this is the cause.
4. **Pane IDs are persistence-stable.** Closing a browser pane and
   immediately reopening one *does* give a new id, but converting a
   browser pane to an explorer (via `openExplorerInPane`) reuses the
   same id on purpose. localStorage persistence keys off id, so changing
   `makeExplorerPane`'s id behavior would silently invalidate saved
   workspaces. See `state/WorkspaceContext.tsx`.
5. **Scrubber state when the `dates` array changes.** The map scrubber
   has an `initialisedRef` flag so first-time mounting sets defaults
   (full-range trim, playhead at start) but subsequent metric / level
   changes preserve the user's playhead — they only clamp it back into
   range when it'd otherwise be invalid. Dropping that flag and
   resetting to `dates.length - 1` causes the playhead to jump to end on
   every interaction.
6. **2-letter country codes in `card.yaml` must be quoted.** YAML 1.1
   parses `NO`, `Y`, `OFF`, etc. as booleans. The pipeline validator
   catches this with a clear error, but if you're hand-editing a card
   for a country that includes Norway you'll trip it. Always quote
   `geography_countries` entries: `"NO"`, `"YES"` (Yemen).

## Conventions that aren't obvious from the code

- **HF cardData is parsed YAML frontmatter.** The HF API
  (`/api/datasets?author=EPI-Eval&full=true`) returns `cardData` as an
  already-parsed object. We don't ship a YAML parser to the browser.
  `data/hf/catalog.ts` defensively coerces fields and silently drops
  malformed entries — corrupt cards never crash the catalog load.
- **Trust `location_id` format over `location_level`.** The schema's
  level label is informational; the *format* of the id (`\d{2}` ⇒ FIPS
  state, `[A-Z]{2}` ⇒ ISO2 country, etc.) is what determines which
  boundary set we render. See `data/locations/detection.ts`.
- **Color scale in the map is `[0, p99]` of all values across all
  dates.** This keeps the chloropleth stable across time so scrubbing
  doesn't reshuffle the scale. Outliers cap at saturated red rather than
  crushing the rest of the data.
- **us-atlas geojson is lazy-loaded** via dynamic `import()`. Counties
  alone is ~9MB; never put it in the main bundle. See
  `data/locations/usAtlas.ts`.
- **The map base style is a self-contained inline JSON** — just an ocean
  background color, no tile provider. Land surface comes from a
  *separate* world-base layer that always renders the world-atlas country
  polygons regardless of which boundary set the dataset uses. See
  `Map/mapConfig.ts` and `Map/BoundaryMap.tsx`. Don't reintroduce a
  terrain basemap (terrain colors were explicitly rejected).
- **Aggregation method comes from the schema.** `pickAggregation` looks
  at the column's declared `aggregation` (sum / mean / max / count /
  rate / proportion / none). Don't hard-code "sum" anywhere — different
  datasets need different reductions and the card declares it.
- **Workspace is never empty.** Closing the last remaining pane resets
  it to a fresh browser pane (`closePane` in WorkspaceContext). Anything
  that assumes `panes.length >= 1` is correct.
- **In-place pane conversion** is how the user's mental model works:
  click "Open data" in a browser pane → that pane becomes an Explorer
  for that source. The pane id is preserved. `openExplorerInPane(id, src)`
  does this; `openExplorer(src)` is the convenience that converts the
  focused pane if it's a browser, else appends a new explorer pane.
- **Cache keys live in localStorage with a 1h TTL.** `data/hf/cache.ts`
  is the only writer; keys are namespaced under
  `epieval-cache:v1:<key>`. Workspace persistence is separate
  (`epieval-workspace:v1`).

## EPI-Eval data shape (so you know what to expect on the wire)

Every dataset's rows carry at minimum: `date`, `location_id`,
`location_level`. Optional row-level columns: `location_id_native`,
`location_name`, `as_of`. Long-format sources (NNDSS, etc.) add
`condition`, `condition_type`, and optionally `case_status`. Beyond
those, value columns vary per source and are declared in `card.yaml`'s
`value_columns`.

`location_id` formats:
- US national: `US`
- US state: 2-digit FIPS (`06`)
- US county: 5-digit FIPS (`06037`)
- Non-US national: ISO 3166-1 alpha-2 (`BR`)
- Non-US first-level subnational: ISO 3166-2 (`BR-SP`) — *not yet
  rendered* on the map
- Below ISO 3166-2: country-prefixed native code
  (`BR-IBGE-3550308`) — *not rendered*
- Point: `point:<lat>,<lon>` — *not rendered*
- Facility: `facility:<id>` — *not rendered*
- Ad-hoc regional: `US-HHS-1` etc. — *not rendered*

Multiple rows per (date, location) is **normal** for long-format
datasets. The chart and map both aggregate before display.

## What's intentionally not in the dashboard

- No backend service. HF is the backend. Don't add one without strong
  reason.
- No mock / synthetic / fabricated values. Empty states only.
- No country-first navigation (the map is one view among many — *don't*
  reintroduce a "select country first" gate).
- No dataset-quality / Rt / risk-score badges. Tier labels were
  explicitly removed from cards.
- No left sidebar. The workspace replaces it.
- No News view. (May come back as a data source / pane type — see
  FOLLOW_UPS.md.)

## Where to look for what

```
src/
├── App.tsx                              providers + WorkspaceShell
├── state/
│   ├── DashboardContext.tsx             catalog only (slim)
│   └── WorkspaceContext.tsx             panes, persistence, actions
├── data/
│   ├── hf/                              HF client + cache + hooks
│   │   ├── catalog.ts                   list + parse cardData
│   │   ├── rows.ts                      paginate /rows + detection helpers
│   │   ├── hooks.ts                     useRecentRows, useDatasetSlice
│   │   └── cache.ts                     localStorage TTL
│   └── locations/
│       ├── detection.ts                 location_id → boundary type
│       └── usAtlas.ts                   lazy state/county geojson
├── components/
│   ├── Layout/WorkspaceShell.tsx        top-level + floating + button
│   ├── Workspace/                       pane shell
│   │   ├── WorkspaceGrid.tsx            1/2/3/4 layouts
│   │   ├── PaneFrame.tsx                header + close + dispatch
│   │   └── BrowserBody.tsx              wraps FeedPage with onOpen
│   ├── Feed/FeedPage.tsx                dataset browser (used in browser panes)
│   ├── Explorer/
│   │   ├── ExplorerBody.tsx             tabs + chart/map + table toggle
│   │   └── DatasetMap.tsx               metric + scrubber + boundary dispatch
│   ├── Graph/
│   │   ├── SourceTimelineChart.tsx      Recharts; aggregation + group-by + series picker
│   │   └── DataTable.tsx                sortable
│   └── Map/
│       ├── BoundaryMap.tsx              MapLibre; feature-state chloropleth
│       ├── countrySelectionLayer.ts     world-atlas helpers
│       └── mapConfig.ts                 inline minimal style + colors
└── styles/globals.css                   (incl. dual-range / playhead CSS)
```

## Testing

- `npm test` (Vitest, node env). 15 tests across `data/hf/*` and
  `state/WorkspaceContext.test.ts`.
- Pure functions get unit tests; UI doesn't have integration tests yet.
- When adding non-trivial logic, factor it into a pure helper and add a
  small test rather than testing through React state.

## Pipeline (write side)

- `upload_pipeline/` is its own Python project with `.venv` and
  `requirements.txt`. Don't import it from the dashboard.
- Each source: `upload_pipeline/sources/<source-id>/{card.yaml,
  ingest.py, data/}`.
- `python -m upload_pipeline.core.validate <source-id>` — schema +
  data-shape validator.
- `python -m upload_pipeline.core.upload <source-id>` — pushes to HF
  using `HF_TOKEN` from `.env`.
- The pipeline does data hashing + diff summary in commit messages so
  re-ingest with no real changes is a no-op.
- Schema in `upload_pipeline/schema/schema_v0.1.md` and
  `vocabularies.yaml` is the source of truth — both pipeline and
  dashboard read it (the dashboard reads parsed cardData, not the raw
  schema).

## Adding a new source

1. Create `upload_pipeline/sources/<id>/{card.yaml, ingest.py}`. Mirror
   the existing sources (`cdc-ilinet`, `ecdc-erviss`, `opendengue`).
2. Run `python <path>/ingest.py` to fetch + write the parquet locally.
3. Run `python -m upload_pipeline.core.validate <id>`. Fix card / data
   issues until it passes.
4. Run `python -m upload_pipeline.core.upload <id>`. Repos default to
   public; if you flip private, the dashboard needs `VITE_HF_TOKEN`.
5. Refresh the dashboard catalog (Refresh button in the Feed); the new
   source should appear.

If the source's `location_id` is ISO 3166-2 / point / facility, the map
view will fall back to its "not yet rendered" amber note. That's fine —
the chart and table will still work.

## Useful environment variables

- `VITE_HF_TOKEN` — only required for *private* HF datasets. Public
  works without auth.
- `VITE_MAP_STYLE_URL` — overrides the inline ocean style. Use only if
  you want an external basemap; keep in mind the user explicitly
  rejected terrain styles.

## When in doubt

- The dashboard never invents values. If you're tempted to fall back to
  "show last observation" or "interpolate", check the conversation
  history first — most synthetic-data fallbacks have been actively
  removed.
- Layout changes that re-introduce vertical scroll on the page (vs.
  inside individual panes) break `scrollbar-gutter: stable` and the
  Explorer's pane content scroll. The shell uses `h-screen
  overflow-hidden`; keep it that way.
- Adding a dependency: check whether a tiny inline helper would do.
  Several near-additions (`yaml`, `idb-keyval`, dual-range component
  libs) were rejected in favor of <50 lines of inline code.
