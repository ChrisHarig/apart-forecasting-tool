# Follow-ups

Stuff to come back to once the multi-pane workspace lands. Captured so we
don't lose them while we're focused on the bigger refactor.

## ~~1. Chart toolbar box alignment~~ — done

`Metric`, `Split by` (renamed from `Group by`), and `Filters` boxes now share
`min-h-[92px]` with `mt-auto` on the meta strips, so the borders line up and
the select controls sit at the same baseline regardless of meta content.

## 2. Year-over-year / season-over-season overlay

Add a chart mode that takes one continuous time axis and slices it into
recurring periods (years, flu seasons, months, ...), then renders one line
per period overlaid on a shared period-relative X axis (e.g. epiweek 40 →
W39). At-a-glance answer to "is this year's flu peak earlier or later than
the last five?".

### Scope

A second chart mode toggle on `SourceTimelineChart` alongside the existing
time-series. Same Metric / Split by / Filters controls underneath. Only the
X axis interpretation and the bucketing change.

### Period model

A small registry of period types the chart knows how to slice on:

```ts
type PeriodKind =
  | { kind: "calendar-year" }
  | { kind: "flu-season"; hemisphere: "northern" | "southern" } // northern: Oct-W40 → May-W21; southern: Apr-W14 → Sep-W39
  | { kind: "calendar-month" }
  | { kind: "fiscal-year"; startMonth: number }                 // catch-all for school-year, etc.
```

Default: `calendar-year`. The user picks period kind from a small dropdown
that appears only when the chart mode is "seasonal."

Per-source default in card metadata (new optional field):

```yaml
# upload_pipeline/schema/schema_v0.1.md additions:
extra:
  default_period:
    kind: flu-season
    hemisphere: northern
```

ECDC ERVISS, NHSN HRD, FluSight Hub → flu-season northern. WHO FluNet →
hemisphere split per row (so the user picks). Mobility, search, mpox →
calendar-year. The dashboard uses this as the default selection but the
user can override.

### X-axis interpretation

The X position becomes "where in the period this date sits":

- calendar-year → day-of-year (1–366) or epiweek (1–53)
- flu-season → epiweek index from the season start (W40 → 1; W39 next year → 53)
- calendar-month → day-of-month (1–31)
- fiscal-year → days since fiscal-year start

Tick labels render in calendar terms ("Oct W40", "Jan W2", ...) while the
underlying numeric x is the period-relative index. Y axis stays the metric
the user picked.

### Period series

Each completed period becomes its own line, identified by its start year
(e.g. "2023-24" for a flu season starting Oct 2023). The current /
in-progress period gets distinct treatment:

- Render as a thicker / brighter line (it's the user's "where are we now")
- Stop drawing at the latest data point — no fake extrapolation
- Optionally: mark with a small "now" annotation

Color encoding: gradient by recency. Older periods → more transparent and
desaturated. Current period → full saturation. (Same `colorByGroup` palette
the existing chart uses, but ordered by period instead of group key.) A
small legend on the right lists periods top→bottom newest→oldest.

### Composition with existing controls

- **Metric**: unchanged. Same y axis, same column.
- **Split by**: still works *within each period series*. If user splits by
  `condition` and there are 3 conditions × 5 seasons = 15 lines. That's a
  lot — show a warning when split × period series > 20, and offer the
  series picker.
- **Filters**: unchanged.
- **Time range scrubber**: in seasonal mode this becomes a *period* scrubber
  — pick which periods to show. Effectively the Series Picker for periods.

### Edge cases

- **Epiweek 53** only exists in some years (~once every 6 years). When a
  period kind uses epiweeks, treat W53 as an extension of W52 for
  comparison purposes (or render as its own tick — TBD per visual review).
- **Partial / in-progress current period**: don't pretend it's complete.
  The line ends where the data ends. Add a "thru W14" annotation.
- **Pre-coverage periods**: a dataset that starts mid-2018 has no full
  pre-2019 flu season. Either skip the partial 2017-18 series or render
  it greyed out with a "partial data" badge.
- **Hemisphere mismatch**: WHO FluNet has both. If the user picks
  flu-season-northern but the data is southern-hemisphere countries, fall
  back to calendar-year and surface a hint. Or split by hemisphere
  automatically.
- **Non-cyclic data**: mobility 2020-2022 has only 2 calendar years and no
  natural seasonality. The toggle should be available but the rendering
  will be sparse. Document that, don't disable it — users can still find
  it useful for "did the same week-of-year look different in COVID year vs
  recovery year?"
- **Cadence mismatch**: monthly + flu-season periods is ~8 points per line.
  Daily + calendar-year is 365. Either is fine.

### Implementation sketch

Where the work lives:

- New `src/components/Graph/SeasonalChart.tsx` rendering Recharts lines per
  period. Reuses metric/split/filter wiring from `SourceTimelineChart`.
- New `src/data/periods.ts` with the period kinds + `dateToPeriodIndex`
  helper that maps `(date, periodKind) → (periodId, x)`.
- Mode toggle on `SourceTimelineChart`: `"time-series" | "seasonal"`.
  Persisted in pane state alongside existing chart settings.
- Per-pane state:
  ```ts
  chart: {
    mode: "time-series" | "seasonal";
    periodKind?: PeriodKind;
    visiblePeriods?: string[];  // null = all
    // existing fields stay
  }
  ```

The bucketing logic in `SeasonalChart` is the only genuinely new piece —
everything else is wiring.

### Effort

A solid day. ~3-4h to ship a v1 (calendar-year + flu-season, no
hemisphere split, no partial-period styling), ~half a day to polish
(period scrubber, partial-period badge, default-period card metadata).

### What can be deferred

- Custom-period definition UI (let users define "summer 2024" or
  arbitrary windows). Power-user feature; skip for v1.
- Period-over-period Δ overlay (each line shows the *difference* from the
  previous period, not the absolute value). Useful but a separate mode.
- Hemisphere auto-split. Handle in v2.

## ~~3. Rename Group by → Split by~~ — done (rename only)

"Group by" → "Split by" in `SourceTimelineChart`. Filter naming stayed.

Per the user's call: filter + split on the same column is left as a
benign no-op (the filter has no effect when the same column is also the
split axis). No predicate to hide it from the menu.

## 4. Boundary loading takes too long or isn't completing

When opening a dataset's map view, polygon loading is noticeably slow and
in some cases doesn't appear to finish. Affects at least the iso3166-2
admin-1 path (vendored at `src/assets/geojson/admin1-50m.geo.json`, ~2.2 MB
gzip-on-disk → ~757 KB gzipped over the wire) and possibly the us-counties
path (~9 MB raw, 252 KB gzipped). The lazy `import("…json")` pattern in
`src/data/locations/{iso3166_2,usAtlas}.ts` ships these as separate Vite
chunks so they don't bloat the main bundle, but the *first* open of an
affected dataset clearly stalls.

Suspects (in rough priority order):

- **Heavy synchronous parse**: `import("…json")` at runtime parses a
  multi-MB JSON on the main thread, blocking the render. We never see a
  loading spinner because the hook setView happens after the parse.
- **No timeout / no progress UX**: if the chunk fetch stalls (HTTP / CDN
  hiccup), the view-loader hook just keeps awaiting forever.
- **Re-running on level/sourceId change**: `useIso3166_2View` is keyed
  on `level`, which is a fresh object per render. Each run kicks off a
  fresh dynamic import (cached after the first, but still re-runs the
  filter step). Worth checking with React DevTools that the cache is in
  fact taking effect after the first load.
- **Country filtering inefficiency**: `loadIso3166_2GeoJson(countries)`
  filters the 2,200-feature collection per call — fine on warm cache,
  but combined with the JSON parse it adds up.

What to try, smallest → biggest:

1. Wrap each view loader in a visible "loading polygons…" state in
   `RenderedMap` so a slow load is at least observable instead of a
   silent "no map yet" gap.
2. Memoize `loadIso3166_2GeoJson(countries)` per country-set, not just
   the underlying file load. Currently the file is cached but the filter
   step runs every call.
3. Convert the admin-1 file from GeoJSON → TopoJSON (~3-5× smaller on
   disk, much smaller after gzip) and decode with `topojson-client` the
   same way `usAtlas` already does. That brings 2.2 MB raw down to ~600 KB
   raw; combined with gzip it's tiny on the wire.
4. Move the JSON parse off the main thread (Web Worker). Bigger lift but
   the right answer if (3) isn't enough.

## Other

Auto ingest and update features
Time series aggregate on year, month, week features
SARIMA and ARIMA and DL-Flusight features. Baseline predictions at any given time stamp.
TAB in browser
Add datasets for predictions, calculate loss, etc.
Crowdsource predictions from people on models? HF dataset of predictions?
Allow for local use of this tool without fetching to HF or anything?