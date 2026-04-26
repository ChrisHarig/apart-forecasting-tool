# EPI-Eval dataset schema — v0.1

Every dataset uploaded to the EPI-Eval HuggingFace org carries a `README.md` whose YAML frontmatter follows this schema. The frontmatter is the canonical metadata; the prose body is for humans.

Two metadata sources, kept separate:

- **Curated** — written by hand (or copied from the manifest). Things you can't derive from the data file: pathogen labels, gating, license, named relations to other datasets, units.
- **Computed** — written by the ingestion pipeline at upload time, by inspecting the actual data file. Things like time coverage, row count, geography unit count. Never hand-edited; always overwritten on re-ingest.

A few entries (notably `value_columns`) are **mixed**: the pipeline writes the structural keys (`name`, `dtype`), and the curator writes the semantic keys (`unit`, `description`, `aggregation`). The validator checks consistency between them on every ingest.

The schema is deliberately small. New fields go under `extra:` and stay there until a contributor explicitly proposes promoting them — promotion is a manual decision, not an automatic threshold (see [Open-ended fields](#open-ended-fields)).

All enum values are validated against [`vocabularies.yaml`](./vocabularies.yaml). See [Validation behavior](#validation-behavior) below.

---

## Frontmatter template

```yaml
---
# ─── HF-recognized fields (drive HF's own search/filter) ───
pretty_name: <human-readable name>
license: <SPDX or HF slug, or "other">
size_categories: [<n<1K|1K<n<10K|10K<n<100K|100K<n<1M|1M<n<10M|10M<n<100M|100M<n<1B|n>1B>]
tags:
  # Denormalized projection of the structured fields below — gives free
  # filtering on the HF site. The structured fields are the source of truth.
  - cadence-<weekly|daily|...>
  - geo-<us|global|br|...>
  - surveillance-<respiratory|arboviral|...>
  - pathogen-<influenza|sars-cov-2|rsv|none>
  - tier-<1|2|3>
  - availability-<open|gated|inactive|...>

# ─── EPI-Eval schema (custom keys, our source of truth) ───
schema_version: "0.1"
source_id: <kebab-case slug, stable, used for cross-references>
source_url: <primary URL>
manifest_section: <e.g. "§1.1">

# Curated — pathogen taxonomy
surveillance_category: <respiratory|arboviral|enteric|mortality|mobility|search|genomic|none>
pathogens: [<influenza|sars-cov-2|rsv|dengue|...>]   # [] if not pathogen-specific

# Curated — provenance / availability
availability: <open|gated|pdf-only|requires-scraping|inactive|unknown>
availability_notes: <free text — required when availability != open>
access_type: <api|csv|socrata|github|ftp|dashboard|...>
tier: <1|2|3>

# Curated — temporal / spatial declarations
cadence: <daily|weekly|biweekly|monthly|quarterly|annual|irregular>
geography_levels: [<national|subnational-state|subnational-county|subnational-region|point|facility>]
geography_countries: [<ISO 3166-1 alpha-2, or "multiple">]

# Curated — named relations (other source_ids in this org)
gold_standard_for: []      # what this serves as ground truth for
vintaged_version_of: null  # null or a single source_id — same data, different view
succeeds: null             # null or a single source_id — institutional successor (different schema, took over the role)
derived_from: []           # raw sources this is computed from

# Curated — vintaging mode
vintaging:
  mode: <full|latest|none>           # 'full' carries every snapshot in the same parquet (requires row-level `as_of`); 'latest' overwrites; 'none' = source not vintaged
  granularity: <daily|weekly|...>    # how often new snapshots land; null when mode != full

# Mixed — pipeline writes name/dtype; curator writes unit/value_type/description/aggregation.
# Validator errors if the curated entries don't match the columns the pipeline saw.
value_columns:
  - name: <str>             # pipeline-set, must match a column in the data file
    dtype: <int|float|str|category>   # pipeline-set
    unit: <free-form string>          # curator-set, required
    value_type: <incident|cumulative|stock|rate|proportion|index|other>  # curator-set, required
    description: <str>                # curator-set, optional
    aggregation: <sum|mean|rate|proportion|count|max|none>  # curator-set, optional

# ─── Computed by the pipeline at ingest (do not hand-edit) ───
computed:
  last_ingested: <ISO 8601 datetime, UTC>
  row_count: <int>
  time_coverage:            # union of intervals; one entry if no large gaps
    - {start: <YYYY-MM-DD>, end: <YYYY-MM-DD or "present">}
  geography_unit_count: <int>
  observed_cadence_days: <int>   # median spacing between consecutive dates
  missing_gaps:                  # gaps > gap_threshold weeks
    - {start: <YYYY-MM-DD>, end: <YYYY-MM-DD>, weeks: <int>}

# ─── Curated notes (structured prose for things humans need to read) ───
notes:
  extra_columns:                # data file columns beyond the row-level convention + value_columns
    - {column: <name>, description: <str>}
  interpretation_caveats:        # per-column semantic gotchas; especially differences from related datasets
    - {column: <name>, caveat: <str>}
  general: <str>                # free prose for anything else; markdown OK

# ─── Free-form, source-specific ───
extra: {}   # arbitrary nested keys; dashboard renders as key-value table
---
```

---

## Field notes

### Pathogen taxonomy

`surveillance_category` is the *syndromic* bucket (what the data is about). `pathogens` is the *specific organisms* the data carries signal for. They're independent. ILI sits in `respiratory` with `pathogens: [influenza, sars-cov-2, rsv]` — the thing it measures (ILI symptoms) is broader than any single pathogen, but the pathogens it surveys are listed. Mobility data is `mobility` with `pathogens: []`.

Allowed pathogen slugs (extend as needed): `influenza`, `influenza-a`, `influenza-b`, `sars-cov-2`, `rsv`, `dengue`, `zika`, `chikungunya`, `west-nile`, `measles`, `pertussis`, `mpox`, `cholera`, `unknown`.

### Availability

This determines whether the pipeline even attempts ingestion. `availability_notes` is required for anything other than `open` — capture *why* it's gated (e.g. "WA state law restricts redistribution", "PDF-only weekly reports, not machine-readable").

### Geography

`geography_levels` is a list because many datasets cover multiple resolutions in the same file (e.g. national + state rolls).

**Critical convention for the data files themselves** (not this card): every row carries a normalized `location_id`:
- US national: `US`
- US state: 2-digit FIPS (`06` = California)
- US county: 5-digit FIPS (`06037`)
- US territory: 2-digit FIPS (`72` = PR)
- Non-US national: ISO 3166-1 alpha-2 (`BR`)
- Non-US first-level subnational: ISO 3166-2 (`BR-SP`)
- Point/facility: `point:<lat>,<lon>` or `facility:<source-specific-id>`

**Below ISO 3166-2 there is no global standard.** ISO 3166-2 only goes one level below national (states/provinces). Brazilian municipalities, Japanese cities, French communes, etc. don't have ISO codes. For these, `location_id` falls back to the country-specific official code, prefixed with the alpha-2 country code so it stays globally unique:

- Brazilian municipalities (IBGE 7-digit): `BR-IBGE-3550308` (São Paulo city)
- Japanese cities (JIS X 0402): `JP-JIS-13104`
- French communes (INSEE): `FR-INSEE-75056`

Every row also carries an optional `location_id_native` column with the source's original code (un-prefixed), and a sibling `location_level` column matching one of the `geography_levels` enum values. Source-native human-readable names (e.g. "São Paulo") may be kept as a third column for traceability, but `location_id` is what the dashboard joins on.

When a source publishes location IDs that don't have a clean conversion to *any* known code system (e.g. ad-hoc catchment areas), that's a quality issue with the source, not something the schema accommodates. Mark `availability_notes` accordingly and consider whether the dataset is worth ingesting as-is.

**Synthetic-prefix codes have a registry** (`upload_pipeline/schema/locations/`). Each YAML file maps a prefix family (`US-METRO-*`, `US-FLUSURV-*`, `US-HHS-*`, etc.) to display names. The validator advisory-warns on unknown synthetic codes so a typo doesn't silently land — but doesn't hard-fail, since per-source synthetic prefixes are normal and grow lazily as sources land. Adding a new code is a YAML PR.

### Cadence

Curated `cadence` is what the source *publishes at*. The pipeline writes `observed_cadence_days` (median diff between consecutive dates) into `computed`; if the two disagree, that's a validation warning, not a hard error — sources occasionally skip weeks.

### Value columns: `value_type` vs `aggregation`

Two related but distinct fields, both required for any non-trivial value column:

- **`value_type`** — what kind of quantity this column *is*. `incident` (new events per period), `cumulative` (running total), `stock` (point-in-time inventory), `rate` (per-population), `proportion` (fraction or percentage), `index` (baseline-relative), `other`.
- **`aggregation`** — how to *combine* multiple rows of this column when zooming out (county → state, week → month).

`value_type` is causally upstream of `aggregation` — it's the more fundamental statement, and it's the one that prevents the most-common epi-data correctness bug: summing a cumulative column. Stating both explicitly is intentional; the validator can warn on inconsistent combinations (e.g. `value_type: cumulative` with `aggregation: sum` is almost always wrong).

When in doubt about `value_type`, ask: "if I had two consecutive rows of this column and added them, would the result mean something coherent?" If yes → `incident` or `count`. If no — if you'd be double-counting, or producing nonsense — → `cumulative`, `stock`, `rate`, `proportion`, or `index`.

### Relations

Four named relations form a small graph across the org. They're semantically distinct — pick the one that actually describes the relationship:

- **`gold_standard_for`** — used by the leaderboard to wire a forecast hub's submissions to its scoring target. e.g. NHSN HRD has `gold_standard_for: [flusight-forecast-hub]`.
- **`vintaged_version_of`** — points to the un-vintaged source. *Same underlying data, different view.* Both are usually still active; one preserves `as_of` history, the other shows the latest revision. Delphi `fluview` has `vintaged_version_of: cdc-ilinet`.
- **`succeeds`** — points to the predecessor that this dataset replaced. *Different schemas, different definitions, sequenced in time.* The predecessor is typically dead. NHSN HRD has `succeeds: hhs-protect` — the underlying reporting system was reorganized, so it's not the same data with a new name; it's a successor with different columns and case definitions. The dashboard must NOT splice these into a single continuous series without explicit normalization.
- **`derived_from`** — points upstream for nowcasts, ensembles, aggregations. A nowcast model output card has `derived_from: [nhsn-hrd, cdc-nssp]`.

All values are EPI-Eval `source_id` slugs. Bidirectional links aren't stored; the dashboard inverts the graph as needed.

### Vintaging

`vintaged_version_of` is a *cross-card relation* — it points to another source that publishes the same data without snapshot history. `vintaging` is a *within-card declaration* — it describes whether *this* card carries snapshot history natively.

- **`vintaging.mode: full`** — every (date, location, …) row is repeated once per snapshot date. The row-level `as_of` column is required; the dashboard groups on `as_of` to render an "as of timestamp X" view, and defaults to the most-recent `as_of` so the card looks single-snapshot until the user opens the time-machine. This is the preferred pattern when the upstream source (Delphi vintaged endpoints, hub `time-series.parquet` files) carries history natively — keep it as one card, not many.

- **`vintaging.mode: latest`** — only the most recent snapshot per (date, location, …) is stored. `as_of` may still be present but isn't a row-key. Use this when storage cost or downstream confusion outweighs the value of the vintage history.

- **`vintaging.mode: none`** — the source publishes a single revision per period and no snapshot dimension exists.

`granularity` documents the cadence at which new snapshots arrive (`daily` for hub `time-series.parquet`, `weekly` for the Delphi vintaged endpoints).

### Time coverage as union of intervals

The pipeline splits `time_coverage` whenever it sees a gap larger than `gap_threshold` (default: 4 weeks for weekly cadence, 14 days for daily). Smaller gaps are treated as noise and don't split the interval; they're recorded under `computed.missing_gaps` if they exceed a smaller per-cadence threshold so the dashboard can flag them. `end: "present"` for live sources whose most recent data is within one cadence period of ingest time.

### Notes

A structured prose block for things a human reader needs but the typed fields can't capture. Three sub-keys, all optional:

- **`extra_columns`** — data file columns beyond the row-level convention (`date`, `location_id`, ...) and `value_columns`. NHSN HRD has `respseason` and `location_name`; CDC NSSP keeps the source's HSA name; etc. One short description per column, so a user opening the Parquet viewer isn't surprised.

- **`interpretation_caveats`** — per-column semantic gotchas, especially differences from how *related* datasets define a similar column. Example for NHSN HRD's `numinptbeds`: "Includes only staffed beds (those with available staff to operate); excludes physically present but unstaffable beds. HHS Protect's analogous column did not enforce this." This is the kind of footnote that determines whether a model trained on one source generalizes to another.

- **`general`** — free prose, markdown allowed. For anything narrative — coverage gaps, known reporting biases, things that took us a while to figure out.

These all render into the README.md body, so contributors and dashboard users see them. The structure (vs. just dumping into prose) means downstream tooling can extract them — e.g. the dashboard can show interpretation caveats inline with column tooltips.

`notes` overlaps with `extra:` in spirit but is the *recommended* place for any prose. Reach for `extra:` only when you have structured machine-readable data that doesn't fit a top-level field.

### Missing data

Parquet stores nulls natively (no CSV `NA` / empty-string ambiguity). Rules the validator enforces:

- **`date`, `location_id`, `location_level`** — required. Null in any of these → hard error.
- **Value columns** — NaN allowed per cell. Time-varying coverage is normal (flu wasn't reported in 2020, RSV wasn't required pre-2024-46, sub-state geographies often have sparse reporting).
- **All-NaN row** (every value column null for one row) — warning, not error. Usually a jurisdiction that reported nothing that week. The dashboard can filter these out by default.
- **All-NaN column across the whole dataset** — warning. Usually means the column doesn't apply to this source's geographies/dates and shouldn't be declared in `value_columns`.
- **Missing column** (declared in card.yaml but absent from the data file) — hard error. This is schema drift, different from NaN.

What this means for ingest scripts: pass missing-source-values through to NaN; don't sentinel them as `-1`, `0`, or `"NA"`. The validator will catch it if you accidentally do.

### Open-ended fields

Anything that doesn't fit goes in `extra`. The dashboard renders unknown keys generically as a key-value table. Examples: mobility's `categories` and `baseline_period`, wastewater's `assay_method`, search-trend's `query_terms`.

**Promotion to a top-level field is manual, not automatic.** When a contributor uploads a dataset, the upload form requires them to map their fields against the existing schema's top-level keys *first*, and only fall back to `extra` for things that genuinely don't fit. This prevents semantic drift (the same concept showing up as `assay`, `assay_method`, and `assay-type` across three different cards). When someone proposes adding a new top-level field, it's reviewed and added in a schema bump (see [What "v0.1" means](#what-v01-means) at the bottom).

For ingestion code we write ourselves, follow the same discipline: if you're tempted to add a key under `extra`, first check whether an existing top-level field captures it.

### Row-level data file convention

Every Parquet/CSV in a dataset repo carries at minimum:

| column              | dtype         | required | notes                                                         |
|---------------------|---------------|----------|---------------------------------------------------------------|
| `date`              | datetime[UTC] | yes      | period-end for weekly data                                    |
| `location_id`       | string        | yes      | normalized per the rules above                                |
| `location_level`    | category      | yes      | one of the `geography_levels` values                          |
| `location_id_native`| string        | optional | source's original code (only when needed for traceability or below ISO 3166-2) |
| `location_name`     | string        | optional | source's human-readable name, for traceability               |
| `condition`         | string        | for case-register sources | row-level condition slug; see [Long-format / case-register data](#long-format--case-register-data) |
| `condition_type`    | category      | required when `condition` is present | one of the `condition_type` enum values |
| `case_status`       | category      | optional | one of the `case_status` enum values; required when source distinguishes confirmed/probable/suspect |
| `topic`             | string        | for non-illness segmented sources | free-form row-level topic slug; see [Topic-segmented sources](#topic-segmented-sources) |
| `topic_type`        | category      | required when `topic` is present | one of the `topic_type` enum values |
| `<value cols>`      | varies        | yes      | source-specific; listed in top-level `value_columns`         |
| `as_of`             | datetime[UTC] | for vintaged sources | snapshot date this row was reported on               |

### Long-format / case-register data

Most surveillance datasets are **time-series** in shape: one row per (date, location), with one column per measure. This is what the row-level convention above defaults to.

But some sources — case-register systems like CDC NNDSS, Brazil SINAN, and other national notifiable-disease feeds — carry **many distinct conditions in a single feed**, often with explicit case-classification tiers. Forcing 120+ conditions into 120+ value columns explodes the schema and makes cross-source filtering by condition awkward. For these sources, use **long format**: one row per (date, location, condition, [case_status]), with a single `count` value column.

**Schema-level signal**: the `condition` row-level column is present and `value_columns` has a single counting column.

**Row-level columns added for long-format sources**:
- `condition` (string, required) — the specific notifiable disease, syndrome, exposure, or outcome this row counts. Slug resolves either to a `pathogens` entry (when `condition_type: pathogen`) or to a `conditions` entry (otherwise).
- `condition_type` (category, required when `condition` is present) — `pathogen | syndrome | exposure | outcome`. Lets the dashboard filter "everything pathogen-related" without confusing pertussis with lead exposure.
- `case_status` (category, optional) — `confirmed | probable | suspect | not-classified`. Required when the source distinguishes certainty tiers (NNDSS does); omit otherwise. **Orthogonal to vintaging**: `case_status` is *label certainty*; `as_of` is *as-of date*. A single (date, location, condition) can have multiple rows — one per `case_status` — and each can have its own `as_of` history.

**Dataset-level metadata for long-format sources**:
- `pathogens` lists all pathogens the dataset *covers*, even if a given row only references one of them. (Same field, used as a summary.)
- `surveillance_category` is typically `notifiable` for these.
- `value_columns` is short (usually one column, named `count` or similar) since the variation has been pushed into row keys.

**Worked example row** (CDC NNDSS, hypothetical):

| date       | location_id | location_level    | condition  | condition_type | case_status | count |
|------------|-------------|-------------------|------------|----------------|-------------|-------|
| 2026-04-12 | 06          | subnational-state | pertussis  | pathogen       | confirmed   | 47    |
| 2026-04-12 | 06          | subnational-state | pertussis  | pathogen       | probable    | 8     |
| 2026-04-12 | 06          | subnational-state | measles    | pathogen       | confirmed   | 0     |
| 2026-04-12 | 06          | subnational-state | acute-flaccid-myelitis | syndrome | confirmed | 1 |
| 2026-04-12 | 06          | subnational-state | lead-exposure | exposure    | not-classified | 12 |

A user querying "all measles data across our org" then writes a single predicate (`condition = 'measles'`) regardless of source.

**Don't use long format when** the source has a small fixed set of measures with rich semantics (NHSN HRD's flu/COVID/RSV admissions + bed counts is wide; NWSS wastewater's per-pathogen viral loads can go either way — choose wide unless contributors will frequently add new pathogens to the same dataset).

### Topic-segmented sources

Not every source's row dimension is a pathogen or syndrome. Mobility data is segmented by *category* (retail, transit, residential); search-trend data is segmented by *query*; news data is segmented by *article subject* or *editorial category*. Forcing those into `condition` would muddy the type — a Wikipedia article isn't a syndrome, a Google Trends query isn't a clinical exposure.

For these sources the schema provides a parallel pair of row-level columns:

- **`topic`** (string, optional) — free-form slug naming the segmentation value (article name, query string, category code).
- **`topic_type`** (category, required when `topic` is present) — `article | search_query | mobility_category | news_category | product_category | intent | other`. The non-illness analog of `condition_type`.

`topic` is **orthogonal to `condition`**: a row can carry either, both, or neither. A news article tagged with both an editorial category (`topic = 'vaccination'`, `topic_type = 'news_category'`) and a pathogen subject (`condition = 'sars-cov-2'`, `condition_type = 'pathogen'`) uses both simultaneously. Wikipedia pageviews use only `topic` because the article isn't a clinical condition. NNDSS uses only `condition`.

**When in doubt:** ask whether the row dimension would naturally appear in a clinician's chart (→ `condition`) or in a marketing / behavioural / informational catalog (→ `topic`).

---

### Validation behavior

The pipeline's validator runs on every ingest and on every PR that touches a dataset card. It enforces:

1. **Required fields are present.** Missing required fields → hard error.
2. **Enum values are registered.** Every enum field (`pathogens`, `surveillance_category`, `cadence`, `geography_levels`, `availability`, `access_type`, `value_columns[].value_type`, `value_columns[].aggregation`, plus row-level `condition`, `condition_type`, and `case_status` for long-format sources) is checked against [`vocabularies.yaml`](./vocabularies.yaml). Unknown values → hard error, but the error message includes **fuzzy-matched suggestions** via Levenshtein/token-set similarity:

   ```
   ERROR: pathogen 'Sars-Cov-2' is not in vocabularies.yaml.
     Did you mean: 'sars-cov-2' (similarity 0.93)?
     If this is genuinely a new pathogen, add it to vocabularies.yaml in a PR.
   ```

   The fuzzy match catches case sensitivity, underscore-vs-hyphen, plural-vs-singular, and typos — the common 90% of "unknown value" errors. Truly new values fail loudly so a human decides whether to extend the registry.

3. **Date columns parse to UTC datetimes.** All columns named `date`, `as_of`, or matching `*_date` are coerced to `datetime[UTC]` at ingest. Failure to parse → hard error with the offending row index.

4. **`location_id` matches the declared `location_level`.** US state-level rows must have a 2-digit FIPS; ISO 3166-2 rows must have a hyphen and a registered country prefix; etc. Failure → hard error pointing at the bad row.

5. **`value_columns` consistency.** Every column listed in the curator's `value_columns` must exist in the data file with the declared dtype, and every value column in the data file (excluding the row-level convention columns and any documented in `notes.extra_columns`) must be listed. Drift → hard error.

5a. **Null patterns.** Required columns (`date`, `location_id`, `location_level`) null → hard error. All-NaN row → warning. All-NaN value column across the entire dataset → warning. Sentinel values that look like missing-data placeholders (`-1`, `999`, `"NA"`) in numeric columns → warning, since these often indicate ingest scripts that failed to coerce missing values to NaN.

6. **`observed_cadence_days` matches `cadence`** (within tolerance). Mismatch → warning, not error. Real-world sources skip weeks.

7. **Curated cross-references resolve.** Every `source_id` in `gold_standard_for`, `vintaged_version_of`, `derived_from` must point to a real dataset in the EPI-Eval org (or be marked as a known external).

The validator runs locally (`python -m upload_pipeline.validate <card.md>`) and in CI on every PR.

---

## What "v0.1" means

We expect to break this. Bump to `0.2` when any required field is renamed, removed, or its enum changes. Adding a new optional field or extending an enum is non-breaking and stays at `0.1`. The pipeline's validator reads `schema_version` and routes to the right validation logic.
