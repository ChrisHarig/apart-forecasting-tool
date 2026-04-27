# EPI-Eval batch ingest — status & schema-fit report

What got built, what's live on HuggingFace, what's still pending, and what
the schema had to grow to fit it.

## Live on HuggingFace (21 datasets)

| source_id | rows | locations | range | predictor cols (T = target, C = covariate) |
|---|---|---|---|---|
| `nhsn-hrd` | 20k | 60 | 2020 → present | T: `totalconfflunewadm`, `totalconfc19newadm`, `totalconfrsvnewadm` · C: bed/ICU stocks |
| `cdc-nssp` | 25k | 51 | 2023 → present | T: `percent_visits` (filtered by condition) |
| `ecdc-erviss` | 10k | 28 | 2021 → present | T: `ili_rate`, `ari_rate` |
| `opendengue` | 100k+ | 129 | 1924 → 2023 | T: `dengue_total` (filtered by case_status) |
| `global-mobility` | 11.7M | 5,306 | 2020 → 2022 | C: 6 mobility-category indices (retail, grocery, parks, transit, workplaces, residential) |
| `owid-covid` | 397k | 238 | 2020 → 2024 | T: `new_cases`, `new_deaths` · C: `icu_patients`, `hosp_patients`, `weekly_*_admissions`, `positive_rate`, vax stocks |
| `nyt-covid` | 2.5M | 3,220 counties | 2020 → 2022 | T: `cases`, `deaths` (cumulative — diff to incident) |
| `jhu-csse-covid` | 225k | 194 | 2020 → 2023 | T: `confirmed`, `deaths` (cumulative) |
| `covid-tracking-project` | 21k | 56 | 2020 → 2021 | T: `positiveIncrease`, `deathIncrease`, `hospitalizedIncrease` · C: `hospitalizedCurrently`, `inIcuCurrently` |
| `owid-mpox` | 154k | 143 | 2022 → present | T: `new_cases`, `new_deaths` · C: cumulative totals |
| `who-tb-burden` | 5.3k | 216 | 2000 → 2024 (annual) | T: `e_inc_num`, `e_mort_num` · C: `e_pop_num`, `e_inc_100k`, `c_cdr` |
| `cdc-nrevss-rsv` | 10k | 10 HHS regions | 2010 → 2020 | T: `rsvpos` · C: `rsvtest` (denominator) |
| `delphi-flusurv` | 9k | 14 catchments | 2003 → present | T: `rate_overall` · C: per-age rates |
| `canada-fluwatch` | 2.7k | 17 | 2025-08 → present | T: `detections`, `percentpositive` · C: `tests` (10 conditions row-level) |
| `flusight-forecast-hub` | 12k | 53 | 2022 → present | T: `value` (flu admissions/wk truth) · C: `weekly_rate` |
| `covid19-forecast-hub` | 4k | 53 | 2024 → present | T: `value` (COVID admissions/wk truth) |
| `rsv-forecast-hub` | 462k | 53 | 2022 → present | T: `value` (RSV admissions/wk) — **fully vintaged via `as_of`** |
| `flu-metrocast-hub` | 132k | 77 metros | 2024 → present | T: `value` (flu admissions/wk per metro) |
| `ukhsa-respiratory` | 1.3k | 1 (England) | 2015 → present | T/C: `positivity`, `admission_rate`, `icu_admission_rate`, `ili_survey_rate`, `survey_participants` (long-on-condition × wide-on-metric) |
| `ukhsa-covid-daily` | 2.3k | 1 (England) | 2020 → present | T: `cases`, `admissions`, `deaths_ons` · C: `occupied_beds`, `pcr_tests` |
| `wikipedia-pageviews` | 43k | 1 global | 2015 → present | C: `views` (covariate; row-level `topic` × 12 articles) |

## Removed 2026-04-26 (11)

Local source folders deleted and `EPI-Eval/<id>-predictions` companions
deleted from HuggingFace. `cdc-ilinet` was previously listed as live in this
report but had never actually been uploaded — confirmed by HF API probe
during cleanup. Re-add by restoring the source folder and re-running
`bootstrap_predictions_repos.py --apply` if any of these become viable later.

| source_id | reason removed |
|---|---|
| `cdc-ilinet` | Delphi `fluview` rate-limit blocks anonymous bulk ingest (60 req/hr; needs 67 calls). Requires Delphi API key. |
| `delphi-fluview-clinical` | Same Delphi rate-limit problem (62 calls). Requires API key. |
| `delphi-nchs-mortality` | Delphi `/epidata/nchs_mortality/` endpoint removed upstream — returns 404. Replace via NCHS data.cdc.gov Socrata if revived. |
| `cdc-nwss-wastewater` | Deferred bulk Socrata fetch never run; not currently needed. |
| `cdc-nndss` | Same — deferred multi-year long-format fetch never run. |
| `hhs-protect-historical` | Deferred 4-year Socrata fetch never run. |
| `who-fluid` / `who-flunet` | Deferred OData paginations never run. |
| `paho-dengue` | PAHO Arbo Portal endpoint returned 502 at build; never verified. OpenDengue covers same countries through 2023. |
| `cdc-dengue-us` | CDC dengue page is client-rendered; superseded by `cdc-nndss` arboviral rows when those are revived. |
| `infodengue-br` | Mosqlimate API requires `X-UID-KEY`; never registered. |

## Schema changes landed this session

All non-breaking; schema_version stays at `0.1`.

1. **`topic` / `topic_type` row-level columns** — non-illness analog of `condition` / `condition_type` for sources whose row dimension is a Wikipedia article, search query, news category, mobility category, etc. `topic_type` enum lives in `vocabularies.yaml`. `wikipedia-pageviews` was refactored onto this. Added `surveillance_category: news` proactively for upcoming editorial / event-feed sources.
2. **`vintaging:` block in card frontmatter** — `mode: full | latest | none` plus `granularity`. `mode: full` requires the row-level `as_of` column (validator enforces). Single card holds the full vintage history; the dashboard filters by `as_of` to render "as of timestamp X" views. `rsv-forecast-hub` is the first source declaring `vintaging: {mode: full, granularity: weekly}`.
3. **Location registry** (`upload_pipeline/schema/locations/`) — `us_states.yaml` + `us_metros.yaml` map FIPS / synthetic codes to display names. Validator advisory-warns on unknown synthetic codes (`US-METRO-*`, `US-FLUSURV-*`, `US-HHS-*`) so typos surface without blocking. `us_metros.yaml` populated from `flu-metrocast-hub` (77 metros).
4. **NNDSS label registry** (`upload_pipeline/schema/nndss_label_mapping.yaml`) — pulled the 30+ label-prefix-to-slug mapping out of `cdc-nndss/ingest.py` and into a YAML the validator can introspect. Adding a new NNDSS label is now a YAML PR.
5. **Pathogen vocab additions** — `adenovirus`, `parainfluenza`, `rhinovirus-enterovirus`, `seasonal-coronavirus`. These were silently dropped from `canada-fluwatch` before — re-ingest jumped it from 5 → 10 conditions, 1,530 → 2,720 rows.
6. **(Skipped per call)** Forecast-output schema for `model-output/` files in the hubs. Truth-only ingests for now.

## Operational gotchas worth remembering

- **HF rejects non-SPDX license slugs.** `ogl-uk-3.0`, `ogl-canada-2.0`, `cc-by-nc-sa-3.0-igo` all fail the upload-time YAML validator. Workaround: `license: other` + `license_name: <slug>` + `license_link: <URL>`. Hit this on UKHSA + Canada FluWatch. Worth adding a pre-upload lint.
- **Sentinel `-1` warnings are not always sentinels.** `global-mobility`'s six value columns legitimately reach -1 (1% below baseline). The validator's flag is informational. `covid-tracking-project`'s `*Increase` -1 values are likely real downward revisions, not sentinels — left as-is.
- **The metro registry warning fires correctly** but doesn't block ingest by design. Adding metros to `us_metros.yaml` shuts the warning up at PR time.

## Reproduce

```bash
source .venv/bin/activate

# Run any built source's ingest:
python -m upload_pipeline.sources.<source_id>.ingest

# Validate locally (validator prints the computed: block on PASS):
python -m upload_pipeline.core.validate <source_id>

# Push to EPI-Eval/<source_id> (creates repo if needed, idempotent re-runs
# only re-upload changed files):
python -m upload_pipeline.core.upload <source_id>
```
