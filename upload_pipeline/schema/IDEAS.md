# Schema ideas — v0.2 and beyond

Things deliberately deferred from v0.1. Recorded so we don't lose them; not yet promoted to the spec.

---

## 1. Cross-dataset column equivalence

**Problem.** When two datasets carry the same underlying signal under different column names (NHSN HRD's `totalconfflunewadm` vs HHS Protect's `previous_day_admission_influenza_confirmed`, both are "weekly new lab-confirmed flu admissions"), there's no way today to express that they're interchangeable.

**Sketch.** A per-column `equivalent_to` field inside `value_columns`:

```yaml
value_columns:
  - name: totalconfflunewadm
    unit: admissions/week
    equivalent_to:
      - source_id: hhs-protect
        column: previous_day_admission_influenza_confirmed
        notes: "HHS Protect reports daily; sum 7 daily values to align with NHSN HRD's weekly cadence."
```

**Why deferred.** We don't yet have two cards in the same hub where this would actually matter. Worth designing once we hit the second flu-admissions dataset and feel the pain.

**Why it matters.** Lets the dashboard offer "stitch these into one continuous series" with explicit, auditable column-level mappings rather than hand-built joins. Also drives the `succeeds` relation's normalization story (HHS Protect → NHSN HRD).

---

## 2. Format export adapters

**Problem.** Other ecosystems (Project Tycho, Hubverse, FluSight target-data format, ECDC ERVISS schema) have their own canonical layouts. Users may want to consume EPI-Eval data in those formats without writing the transformation themselves.

**Sketch.** A `upload_pipeline/exporters/` module with one adapter per target format:

```
upload_pipeline/exporters/
├── tycho.py        # canonical → Tycho
├── hubverse.py     # canonical → Hubverse target-data
└── flusight.py     # canonical → FluSight target_data.csv
```

Each adapter takes our canonical Parquet + card metadata and emits the target format's file. Available as a CLI subcommand and as a downloadable export from the dashboard.

**Why deferred.** Adapters are only valuable once we have stable, well-curated data on the canonical side. Build the canonical side correctly first.

**Constraint this places on v0.1.** Our canonical form must be a *superset* of every format we'd want to export to. Each new adapter is a chance to discover we lack a field — when we hit one, that field is a candidate for promotion to a top-level schema field. (Tycho's `PartOfCumulativeCountSeries` already exposed one such gap during initial scoping; that's why `value_type` is in v0.1.)

---

## 3. Period-start row-level column

**Problem.** Our row-level convention has `date` (period-end) but no `period_start`. For weekly data this is fine (start = end - 6 days), but irregular-cadence sources or sources with explicit non-overlapping periods may need both.

**Sketch.** Optional `period_start: datetime[UTC]` row-level column. When absent, period is implied by `cadence` and `date`.

**Why deferred.** Haven't hit a source where it's needed yet. Add when we do; non-breaking change.

---

## 4. ~~Multi-pathogen tagging at the row level~~ — **resolved in v0.1**

Originally deferred, pulled forward when scoping NNDSS revealed the wide-format approach didn't scale (120+ conditions, multiple case-classification tiers, mix of pathogens and non-pathogen conditions). The row-level `condition`, `condition_type`, and `case_status` columns are now part of the spec — see [Long-format / case-register data](./schema_v0.1.md#long-format--case-register-data).

---

## 5. Multiple table types

**Problem.** Our row-level convention is fundamentally a *time series* shape: one row per (date, location, [optional row-key columns]) with value columns. v0.1 stretches this with optional row keys (`condition`, `case_status`) so case-register sources like NNDSS fit. But forecast archives like FluSight Forecast Hub really want eight row keys (`team × model × reference_date × target × horizon × location × output_type × output_type_id`), which is starting to strain the "time series with extras" framing.

**Sketch.** Promote table type to a first-class dataset-level field:

```yaml
table_type: time_series | case_register | forecast_archive | model_output | metadata
```

Each table type has its own row-level convention. The schema spec gains a section per table type rather than bolting more optional columns onto a single convention. Validators dispatch on `table_type`.

**Why deferred.** v0.1's "time series with optional row keys" handles 17 of the 19 Tier-1 datasets cleanly. The two outliers (FluSight + COVID-19 Forecast Hubs) we can ingest in Hubverse format with `surveillance_category: forecasts` and document the row-key proliferation in `extra:`. Promote `table_type` to a first-class field once we have ≥3 sources that genuinely don't fit time-series shape and the workaround starts hurting.

**Why it matters.** Today the dashboard's time-series component can render any dataset by joining on (date, location). Once `table_type` exists, the dashboard can pick the right component (time-series chart vs. forecast-fan-chart vs. case-register-table) automatically based on the dataset card.

---

## 6. Provenance / lineage

**Problem.** When the pipeline pulls from a source on 2026-04-25 and re-pulls on 2026-05-02, what's the audit trail for what changed?

**Sketch.** Each ingest creates an HF dataset commit with structured commit message metadata: source URL, fetch timestamp, row delta, schema version. The card already gets `last_ingested`; this adds a queryable history.

**Why deferred.** HF's git history gives us most of this for free at the file level. Formalize when we need to programmatically diff ingests.
