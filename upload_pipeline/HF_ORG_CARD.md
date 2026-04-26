# EPI-Eval

A curated collection of large epidemiological datasets, normalized to a single
schema so they can be searched, joined, and benchmarked against each other.

## What we track

Time-series surveillance data on infectious disease — primarily respiratory
viruses (flu, COVID-19, RSV) and arboviral disease (dengue, Zika,
chikungunya), with smaller coverage of notifiable, mortality, wastewater, and
behavioural / search signals. Sources come from CDC, WHO, ECDC, PAHO, OWID,
and national public-health agencies; we re-publish them as Parquet with a
consistent set of row-level columns (`date`, `location_id`, `location_level`,
optional `condition` / `case_status` / `as_of`) and a metadata header
describing pathogens, geography, cadence, and per-column units.

## Why

Forecasting and modeling work routinely stalls on data plumbing — finding the
canonical version of a series, normalizing geography codes, reconciling
reporting cadences, tracking when a source was last revised. The goal of this
org is to do that work once, in the open, so models can compete on substance
rather than on whose ingest scripts are less broken.

## Schema

Every dataset card on this org uses the same frontmatter format
([schema v0.1](https://github.com/ChrisHarig/apart-forecasting-tool/blob/main/upload_pipeline/schema/schema_v0.1.md)),
validated against a controlled vocabulary
([`vocabularies.yaml`](https://github.com/ChrisHarig/apart-forecasting-tool/blob/main/upload_pipeline/schema/vocabularies.yaml)).
Curated metadata (pathogens, license, units) lives alongside computed metadata
(time coverage, row count, observed cadence) generated at ingest.

## Contributing a dataset

The ingest pipeline is in
[`apart-forecasting-tool/upload_pipeline`](https://github.com/ChrisHarig/apart-forecasting-tool/tree/main/upload_pipeline).
A new dataset is one `ingest.py` + `card.yaml` under
`upload_pipeline/sources/<source_id>/`; the validator confirms schema fit
before upload.

## Status

Active. Coverage and dataset list grow through PRs to the upload pipeline.
