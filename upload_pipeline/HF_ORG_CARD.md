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
before upload. Each new truth dataset auto-creates an empty
`<id>-predictions` companion at upload time.

## Datasets (21)

### Respiratory

| Dataset | Pathogens | Geography | Cadence |
| --- | --- | --- | --- |
| [CDC FluSurv-NET — weekly flu hospitalisation rates](https://huggingface.co/datasets/EPI-Eval/delphi-flusurv) | influenza | US | weekly |
| [CDC NHSN Hospital Respiratory Data (HRD)](https://huggingface.co/datasets/EPI-Eval/nhsn-hrd) | influenza, sars-cov-2, rsv | US | weekly |
| [CDC NREVSS — weekly RSV test specimens and positives](https://huggingface.co/datasets/EPI-Eval/cdc-nrevss-rsv) | rsv | US | weekly |
| [COVID Tracking Project — US states daily (archived)](https://huggingface.co/datasets/EPI-Eval/covid-tracking-project) | sars-cov-2 | US | daily |
| [COVID-19 Forecast Hub — hospital admissions target](https://huggingface.co/datasets/EPI-Eval/covid19-forecast-hub) | sars-cov-2 | US | weekly |
| [ECDC ERVISS — ILI/ARI primary-care consultation rates](https://huggingface.co/datasets/EPI-Eval/ecdc-erviss) | influenza, sars-cov-2, rsv | multiple (30 countries) | weekly |
| [Flu MetroCast Hub — sub-state flu hosp forecast target](https://huggingface.co/datasets/EPI-Eval/flu-metrocast-hub) | influenza | US | weekly |
| [FluSight Forecast Hub — flu hospital admission target](https://huggingface.co/datasets/EPI-Eval/flusight-forecast-hub) | influenza | US | weekly |
| [JHU CSSE COVID-19 — global daily (archived)](https://huggingface.co/datasets/EPI-Eval/jhu-csse-covid) | sars-cov-2 | multiple | daily |
| [NYT COVID-19 — US county daily](https://huggingface.co/datasets/EPI-Eval/nyt-covid) | sars-cov-2 | US | daily |
| [OWID COVID-19 — global daily compiled](https://huggingface.co/datasets/EPI-Eval/owid-covid) | sars-cov-2 | multiple | daily |
| [PHAC Respiratory Virus Detection Surveillance — Canada weekly](https://huggingface.co/datasets/EPI-Eval/canada-fluwatch) | influenza, influenza-a, influenza-b +7 | CA | weekly |
| [RSV Forecast Hub — RSV hospital admissions target](https://huggingface.co/datasets/EPI-Eval/rsv-forecast-hub) | rsv | US | weekly |
| [UKHSA Dashboard — England COVID-19 daily metrics](https://huggingface.co/datasets/EPI-Eval/ukhsa-covid-daily) | sars-cov-2 | GB | daily |
| [UKHSA Dashboard — England flu / COVID-19 / RSV weekly](https://huggingface.co/datasets/EPI-Eval/ukhsa-respiratory) | influenza, sars-cov-2, rsv | GB | weekly |

### Syndromic / ED

| Dataset | Pathogens | Geography | Cadence |
| --- | --- | --- | --- |
| [CDC NSSP / ESSENCE — ED visits for ILI / COVID / RSV](https://huggingface.co/datasets/EPI-Eval/cdc-nssp) | influenza, sars-cov-2, rsv | US | weekly |

### Arboviral

| Dataset | Pathogens | Geography | Cadence |
| --- | --- | --- | --- |
| [OpenDengue — national dengue case counts (V1.3)](https://huggingface.co/datasets/EPI-Eval/opendengue) | dengue | multiple | irregular |

### Mobility & contact

| Dataset | Pathogens | Geography | Cadence |
| --- | --- | --- | --- |
| [Google Community Mobility Reports — global daily](https://huggingface.co/datasets/EPI-Eval/global-mobility) | — | multiple | daily |

### Search & behavioural

| Dataset | Pathogens | Geography | Cadence |
| --- | --- | --- | --- |
| [Wikipedia pageviews — disease-article daily views](https://huggingface.co/datasets/EPI-Eval/wikipedia-pageviews) | influenza, sars-cov-2, rsv +6 | multiple | daily |

### Notifiable / other

| Dataset | Pathogens | Geography | Cadence |
| --- | --- | --- | --- |
| [OWID Mpox — global daily compiled](https://huggingface.co/datasets/EPI-Eval/owid-mpox) | mpox | multiple | daily |
| [WHO Global TB — annual country estimates](https://huggingface.co/datasets/EPI-Eval/who-tb-burden) | tuberculosis | multiple | annual |

## Predictions

Each truth dataset has a companion `EPI-Eval/<id>-predictions` repo that
accumulates community-submitted forecasts. Schema is long-format: one row per
`(target_date, [dim values…], quantile, value)`, with `quantile = NULL`
reserved for the point estimate. Forecasters submit through the
[EPI-Eval dashboard](https://github.com/ChrisHarig/apart-forecasting-tool);
a maintainer reviews each PR before merging, and merged predictions show up
on the corresponding truth dataset's *Show predictions* toggle in the
dashboard, with a per-submitter leaderboard (MAE / WIS / rWIS / coverage).

## Status

Active. Coverage and dataset list grow through PRs to the upload pipeline.
