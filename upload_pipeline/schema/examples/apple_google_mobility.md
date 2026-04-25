---
# ─── HF-recognized ───
pretty_name: Apple & Google Community Mobility Reports (archived)
license: other  # Apple ToU + Google CC BY 4.0 — mixed; see availability_notes
size_categories:
  - 10M<n<100M
tags:
  - cadence-daily
  - geo-global
  - surveillance-mobility
  - pathogen-none
  - tier-3
  - availability-inactive

# ─── EPI-Eval schema ───
schema_version: "0.1"
source_id: apple-google-mobility
source_url: https://github.com/ActiveConclusion/COVID19_mobility
manifest_section: "§15.7"

surveillance_category: mobility
pathogens: []   # mobility data has no associated pathogen

availability: inactive
availability_notes: >
  Apple Mobility Trends Reports were discontinued 2022-04-14. Google COVID-19
  Community Mobility Reports were discontinued 2022-10-15. Both are static
  archives only; no further updates expected. Snapshot maintained at the
  GitHub mirror in source_url. Apple data is under Apple ToU (redistribution
  permitted with attribution); Google data is CC BY 4.0.
access_type: github
tier: 3

cadence: daily
geography_levels:
  - national
  - subnational-state
  - subnational-county
  - subnational-region   # Apple uses cities; Google uses sub-regions
geography_countries:
  - multiple

gold_standard_for: []
vintaged_version_of: null
derived_from: []

# ─── Mixed: pipeline writes name/dtype, curator writes unit/description/aggregation ───
value_columns:
  - name: provider
    dtype: category
    unit: enum
    value_type: other
    description: "Vendor identifier; one of: apple, google"
    aggregation: none
  - name: metric
    dtype: category
    unit: enum
    value_type: other
    description: Specific mobility metric — see extra.metrics_apple / extra.metrics_google for the enumeration
    aggregation: none
  - name: value
    dtype: float
    # Unit varies by row depending on (provider, metric); see extra.units.
    # We accept this as a documented quirk rather than splitting into separate columns;
    # downstream consumers must condition on `provider` before interpreting.
    unit: "varies by row — see extra.units"
    value_type: index
    description: "Mobility indicator value (Apple: index where 100=baseline; Google: % change vs. day-of-week baseline)"
    aggregation: mean

# ─── Computed by pipeline ───
computed:
  last_ingested: "2026-04-25T14:00:00Z"
  row_count: 14820000
  time_coverage:
    - {start: "2020-01-13", end: "2022-04-14"}    # Apple coverage
    - {start: "2020-02-15", end: "2022-10-15"}    # Google coverage
  geography_unit_count: 4823
  observed_cadence_days: 1
  missing_gaps:
    # Apple paused county-level data briefly during a 2021 schema migration.
    - {start: "2021-04-12", end: "2021-05-03", weeks: 3}

extra:
  # Mobility-specific fields — exactly the kind of thing the schema's
  # open-ended `extra` block is designed for.
  metrics_apple:
    - driving        # % change in driving direction requests
    - walking
    - transit        # not available in all geographies
  metrics_google:
    - retail_and_recreation
    - grocery_and_pharmacy
    - parks
    - transit_stations
    - workplaces
    - residential
  baseline_period_apple: "2020-01-13"   # baseline = 100
  baseline_period_google: {start: "2020-01-03", end: "2020-02-06"}  # median day-of-week value
  units:
    apple: "index (baseline = 100)"
    google: "percent change vs. baseline"
  not_directly_comparable: true  # apple and google use different baselines and metrics
  reidentification_note: >
    Both providers applied differential privacy / k-anonymity thresholds; expect
    suppression in low-population geographies.
---

# Apple & Google Community Mobility Reports (archived)

Daily mobility indicators from Apple Maps direction requests and Google Maps location-history aggregations, covering the early-pandemic period through late 2022. Ingested from a community-maintained GitHub mirror (the original Apple/Google portals are offline).

Useful as a **historical covariate** for retrospective COVID-era model evaluation. Not suitable as a live signal — both feeds are dead.

## Pipeline notes

- Single ingestion run; no recurring cron needed (source is static).
- Apple and Google rows live in the same table, distinguished by `provider`. They use different baselines and metric definitions — see `extra.not_directly_comparable`. The dashboard should not allow naive cross-provider comparison without normalization.
- Country-level data is available globally; sub-state coverage is partial and varies by provider.

## Known caveats

- Apple required a steady volume of direction requests to publish a value; rural/low-traffic areas have sparse data.
- Google's "residential" metric is duration-based (% of time at home), unlike the others which are visit-count-based; treat separately.
