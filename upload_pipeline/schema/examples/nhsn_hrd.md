---
# ─── HF-recognized ───
pretty_name: CDC NHSN Hospital Respiratory Data (HRD)
license: other  # US federal works — public domain in US, no SPDX slug
size_categories:
  - 100K<n<1M
tags:
  - cadence-weekly
  - geo-us
  - surveillance-respiratory
  - pathogen-influenza
  - pathogen-sars-cov-2
  - pathogen-rsv
  - tier-1
  - availability-open

# ─── EPI-Eval schema ───
schema_version: "0.1"
source_id: nhsn-hrd
source_url: https://data.cdc.gov/Public-Health-Surveillance/Weekly-Hospital-Respiratory-Data-HRD-Metrics-by-Ju/ua7e-t2fy/about_data
manifest_section: "§1.1"

surveillance_category: respiratory
pathogens:
  - influenza
  - sars-cov-2
  - rsv

availability: open
availability_notes: null
access_type: socrata
tier: 1

cadence: weekly
geography_levels:
  - national
  - subnational-state
geography_countries:
  - US

gold_standard_for:
  - flusight-forecast-hub
  - covid19-forecast-hub
  - rsv-forecast-hub
vintaged_version_of: null
succeeds: hhs-protect      # different reporting system; do not splice rows directly
derived_from: []

# ─── Mixed: pipeline writes name/dtype, curator writes unit/description/aggregation ───
value_columns:
  - name: totalconfflunewadm
    dtype: int
    unit: admissions/week
    value_type: incident
    description: New laboratory-confirmed influenza hospital admissions
    aggregation: sum
  - name: totalconfc19newadm
    dtype: int
    unit: admissions/week
    value_type: incident
    description: New laboratory-confirmed COVID-19 hospital admissions
    aggregation: sum
  - name: totalconfrsvnewadm
    dtype: int
    unit: admissions/week
    value_type: incident
    description: New laboratory-confirmed RSV hospital admissions
    aggregation: sum
  - name: numinpatbeds
    dtype: int
    unit: beds
    value_type: stock
    description: Total staffed inpatient beds (capacity denominator) — point-in-time
    aggregation: mean
  - name: numinpatbedsocc
    dtype: int
    unit: beds
    value_type: stock
    description: Total staffed inpatient beds occupied — point-in-time
    aggregation: mean

# ─── Computed by pipeline (overwritten on each ingest) ───
computed:
  last_ingested: "2026-04-25T14:00:00Z"
  row_count: 287560
  time_coverage:
    - {start: "2024-11-09", end: "present"}
  geography_unit_count: 56  # 50 states + DC + 5 territories
  observed_cadence_days: 7
  missing_gaps: []

extra:
  reporting_change: "Hospital reporting became voluntary 2024-05-01 to 2024-11-09; mandatory reporting resumed under NHSN HRD starting epiweek 2024-46."
  case_definition_url: https://www.cdc.gov/nhsn/psc/respiratory-data.html
---

# CDC NHSN Hospital Respiratory Data (HRD)

Weekly counts of new admissions for laboratory-confirmed influenza, COVID-19, and RSV from acute-care hospitals reporting to NHSN. Replaces the HHS Protect dataset that ran 2020–2024.

This is the **scoring target** for the FluSight, COVID-19, and RSV Forecast Hubs from the 2024–25 season onward.

## Pipeline notes

- Pulled via Socrata API (`ua7e-t2fy`); paginated with `$limit=50000`.
- Source uses jurisdiction names; pipeline maps to 2-digit FIPS in `location_id`.
- Vintaged variant available via Delphi epidata (`hhs` endpoint, `as_of` parameter); see `nhsn-hrd-vintaged` for the version-controlled snapshots.

## Known caveats

Reporting completeness varies by jurisdiction in the early weeks of the mandatory reporting era (epiweek 2024-46 onward). Some territories have sparse reporting; check `numinpatbeds` for denominator coverage before using rates.
