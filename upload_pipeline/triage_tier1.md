# Tier-1 dataset triage

First-pass feasibility assessment for the 19 Tier-1 datasets. Drawn from the manifest (`data/manifest/EPI-EVAL_datasets_table.csv`) without web verification — items marked **VERIFY** need a live check before we write the ingest module.

Verdict legend:
- 🟢 **Clear win** — open programmatic access, fits schema cleanly, build first.
- 🟡 **Moderate** — workable with known friction (deprecated endpoint, big schema, intermittent server).
- 🔴 **Hard** — requires scraping, gated, or upstream is unstable. Scope-out of PoC unless we have a strong reason.

---

## Summary table

| Verdict | Section | source_id (proposed)        | Dataset                                | Access            | Blocker / friction |
|---------|---------|-----------------------------|----------------------------------------|-------------------|---------------------|
| 🟢      | §1.1    | `nhsn-hrd`                  | CDC NHSN HRD                           | Socrata           | none                |
| 🟢      | §1.2    | `cdc-ilinet`                | CDC ILINet (FluView)                   | Delphi epidata    | none                |
| 🟢      | §1.8    | `cdc-nssp`                  | CDC NSSP / ESSENCE (aggregate)         | Socrata           | none                |
| 🟢      | §3.1    | `delphi-covidcast`          | Delphi COVIDcast API                   | Delphi REST       | meta-source: 500+ signals; pick a subset |
| 🟢      | §4.1    | `flusight-forecast-hub`     | FluSight Forecast Hub                  | GitHub raw        | Hubverse format    |
| 🟢      | §4.2    | `covid19-forecast-hub`      | COVID-19 Forecast Hub                  | GitHub raw        | Hubverse format    |
| 🟢      | §5.3    | `ecdc-erviss`               | ECDC ERVISS                            | GitHub CSV        | none                |
| 🟡      | §2.1    | `cdc-nndss`                 | CDC NNDSS                              | Socrata           | 120+ conditions — wide-format or long-format decision |
| 🟡      | §5.1    | `who-flunet`                | WHO FluNet                             | CSV download      | URL changes; geography normalization for 113 countries |
| 🟡      | §5.4    | `sentinelles-france`        | Réseau Sentinelles France              | REST API          | OData endpoint EOL'd 2024-12 — **VERIFY** what's still live |
| 🟡      | §6.1    | `opendengue`                | OpenDengue                             | figshare CSV      | static archive (no live updates); fine as historical baseline |
| 🟡      | §6.3    | `infodengue-br`             | InfoDengue (Brazil)                    | Mosqlimate API    | 5,570 BR municipalities — IBGE codes; **VERIFY** API auth/limits |
| 🟡      | §23.1c  | `singapore-wid`             | Singapore Weekly Infectious Disease    | data.gov.sg API   | small geographic scope but clean access |
| 🟡      | §23.1e  | `epiclim-india`             | EpiClim India                          | Zenodo            | one-shot download; may need updates separately |
| 🔴      | §5.7    | `infogripe-br`              | Brazil InfoGripe / SIVEP-Gripe         | Web + CSV (slow)  | "Fiocruz server intermittent" — needs retry/tolerance |
| 🔴      | §23.1a  | `taiwan-cdc-opendata`       | Taiwan CDC Open Data                   | Portal API        | 200+ datasets — sub-triage required to pick which |
| 🔴      | §23.1b  | `hk-chp`                    | Hong Kong CHP                          | Web only          | likely scraping; **VERIFY** if any download endpoint exists |
| 🔴      | §23.1d  | `india-idsp`                | India IDSP                             | Web scrape        | manifest explicitly says scrape — hardest of the group |
| 🔴      | §23.2a  | `argentina-snvs`            | Argentina SNVS / Boletín Integrado     | Web only          | bulletin format; likely PDF/HTML extraction |
| 🟡      | §23.6a  | `usda-aphis-hpai`           | USDA APHIS HPAI Livestock              | Dashboard         | **VERIFY** if hidden JSON endpoint exists; H5N1 worth the effort |

7 🟢 / 8 🟡 / 5 🔴 (the §23.6a HPAI one I bumped to 🟡 because H5N1 is too important to drop without checking for a JSON endpoint).

---

## Recommended PoC scope

Build the **7 🟢 clear-win sources first**. They give us:

- The FluSight scoring target (NHSN HRD)
- The classic flu signal (ILINet)
- ED visit syndromic (NSSP)
- A meta-API covering many additional signals (Delphi COVIDcast)
- Two US forecast hubs (FluSight, COVID-19) → the leaderboard has actual submissions to score against
- A non-US analog (ERVISS) so the pipeline is tested on >1 country from day one

That's enough to demonstrate the full pipeline (ingest → validate → upload → dashboard → leaderboard) end-to-end. Add 🟡 sources once each is verified. Defer 🔴 sources unless one becomes blocking.

---

## Per-dataset notes

### 🟢 §1.1 NHSN HRD → `nhsn-hrd`

- **Access:** Socrata endpoint `data.cdc.gov/resource/ua7e-t2fy.json` (paginated `$limit=50000`, `$offset=...`).
- **Cadence:** weekly (epiweek period-end).
- **Geography:** US states + DC + 5 territories; map jurisdiction names → 2-digit FIPS.
- **Vintaged:** yes via Delphi `hhs` endpoint — can be a separate `nhsn-hrd-vintaged` dataset later.
- **Schema fit:** wide format with one column per (pathogen × measure). Maps cleanly to our `value_columns`.
- **Build order:** **first**. This is the FluSight target — without it, the leaderboard doesn't work.

### 🟢 §1.2 CDC ILINet → `cdc-ilinet`

- **Access:** Delphi epidata `fluview` endpoint. Python client available (`pip install delphi-epidata`).
- **Cadence:** weekly, going back to 1997.
- **Geography:** national + 10 HHS regions + 50 states.
- **Vintaged:** yes — Delphi preserves `as_of` for revisions.
- **Schema fit:** `wili` (weighted % ILI) → `value_type: proportion`, `aggregation: rate`. Counts of patients/providers as separate columns.
- **Build order:** second. Cleanest API, small data volume.

### 🟢 §1.8 CDC NSSP → `cdc-nssp`

- **Access:** Socrata `data.cdc.gov/resource/vutn-jzwm.json`. Delphi `nssp` is also available.
- **Cadence:** weekly.
- **Geography:** national/state/sub-state (HSA — Health Service Area).
- **Vintaged:** yes via Delphi.
- **Schema fit:** % visits for ILI/COVID/RSV → `value_type: proportion`.

### 🟢 §3.1 Delphi COVIDcast → `delphi-covidcast`

- **Access:** Delphi REST API with mature R/Python clients.
- **Cadence:** mixed; varies by signal.
- **Vintaged:** full vintaging — `as_of` works for every signal.
- **Friction:** 500+ signals. We don't ingest all of them; pick a starter set (`hhs.confirmed_admissions_influenza`, `chng.smoothed_outpatient_cli`, `safegraph.full_time_work_prop`, etc.). Each Delphi source × signal combination is a candidate for its own EPI-Eval dataset, OR a single `delphi-covidcast-<source>` dataset with multiple signals as columns.
- **Decision needed:** one big `delphi-covidcast` dataset with many signals as columns, or one dataset per Delphi source. Lean toward "one per source" so the cards stay coherent.

### 🟢 §4.1 FluSight Forecast Hub → `flusight-forecast-hub`

- **Access:** raw GitHub files at `cdcepi/FluSight-forecast-hub`. Per-team CSVs in `model-output/`.
- **Format:** **Hubverse**. We can adopt their structure for the rows directly.
- **Schema fit:** this is forecasts, not surveillance. `surveillance_category: forecasts`, `pathogens: [influenza]`, `gold_standard_for: []`, `derived_from: [nhsn-hrd]`.
- **Note:** ingesting forecasts is different from ingesting truth — it's an archive-of-submissions, not a time series. Each row is `(team, model, reference_date, target, horizon, location, output_type, output_type_id, value)`. Worth treating as a special case in the schema later.

### 🟢 §4.2 COVID-19 Forecast Hub → `covid19-forecast-hub`

- Same pattern as §4.1. Different repo (`CDCgov/covid19-forecast-hub`), different pathogen.

### 🟢 §5.3 ECDC ERVISS → `ecdc-erviss`

- **Access:** raw GitHub at `EU-ECDC/Respiratory_viruses_weekly_data`. CSVs.
- **Cadence:** weekly.
- **Geography:** 30 EU/EEA countries — ISO 3166-1 alpha-2 should map cleanly.
- **Vintaged:** yes via git history (each weekly commit is a snapshot).

---

### 🟡 §2.1 CDC NNDSS → `cdc-nndss`

- **Access:** Socrata `data.cdc.gov/resource/x9gk-5huc.json`. Also CDC WONDER.
- **Friction:** 120+ conditions in one feed. Two options:
  1. **Wide format**: one column per condition × measure (current week, cumulative, prior 5-year max). Works but `value_columns` gets huge.
  2. **Long format**: one row per (date × location × condition × measure). Requires the row-level pathogen field we deferred to v0.2.
- **Recommendation:** ingest in long format and add the deferred `pathogen` row-level column. NNDSS forces the issue; better to confront it on this source than defer further.

### 🟡 §5.1 WHO FluNet → `who-flunet`

- **Access:** CSV from `who.int/tools/flunet`. Direct download URL.
- **Friction:** WHO has historically moved URLs. Need a stable resolver / fallback to scrape the page for the current download link.
- **Geography:** 113 countries — ISO 3166-1 should cover, but WHO uses its own country names; need a names→ISO crosswalk.

### 🟡 §5.4 Réseau Sentinelles France → `sentinelles-france`

- **Access:** REST API at `sentiweb.fr/api/v1/datasets/rest/`. **VERIFY** — manifest says OData endpoint EOL'd 2024-12-01; need to confirm REST is the live replacement and what its schema looks like now.
- **Geography:** France national + ~13 regions (post-2016 redécoupage). Map to ISO 3166-2 (`FR-IDF`, etc.).

### 🟡 §6.1 OpenDengue → `opendengue`

- **Access:** static CSV on figshare.
- **Static archive** — no recurring ingestion needed. One-shot download, mark `availability: inactive` even though the project itself is active (the data file is). Or `availability: open` with a note that updates are sporadic figshare uploads.

### 🟡 §6.3 InfoDengue → `infodengue-br`

- **Access:** Mosqlimate API at `api.mosqlimate.org`. **VERIFY** auth, rate limits, and exact endpoint/response shape.
- **Geography:** 5,570 Brazilian municipalities — IBGE 7-digit codes, no ISO 3166-2 below state level. Use `BR-IBGE-XXXXXXX` per the schema's native-fallback rule.

### 🟡 §23.1c Singapore WID → `singapore-wid`

- **Access:** data.gov.sg API. Open, well-documented.
- **Friction:** ~30 diseases, weekly.

### 🟡 §23.1e EpiClim India → `epiclim-india`

- **Access:** Zenodo record `14580510`. One-shot download.
- **Friction:** Zenodo records can be versioned (`/records/<id>/versions`); pin the version we ingest.

### 🟡 §23.6a USDA APHIS HPAI → `usda-aphis-hpai`

- **Access:** dashboard. **VERIFY** if there's a hidden JSON/CSV endpoint behind the dashboard (often is — check Network tab).
- **Why bump from 🔴:** H5N1 in dairy cattle is genuinely important for early-warning and we should make a real attempt.

---

### 🔴 §5.7 Brazil InfoGripe → `infogripe-br`

- **Access:** Web + CSV via info.gripe.fiocruz.br. Server intermittently down.
- **Friction:** retry/backoff logic mandatory; ingest may fail for days at a stretch. SARI hospitalization data is high-quality when accessible.
- **Note:** §5.7b OpenDataSUS / SRAG raw is the underlying record-level data — Tier 2, but possibly more reliable as an alternative source.

### 🔴 §23.1a Taiwan CDC Open Data → `taiwan-cdc-opendata`

- 200+ datasets behind a portal API. Sub-triage needed: which 1-3 are actually useful for our PoC? Probably weekly ILI sentinel + lab-confirmed flu. Defer until we narrow.

### 🔴 §23.1b Hong Kong CHP → `hk-chp`

- Web only per manifest. **VERIFY** — many gov portals expose CSV downloads on the dashboard pages even when not listed as APIs. If yes, bump to 🟡; if not, defer (scraping HTML weekly is fragile).

### 🔴 §23.1d India IDSP → `india-idsp`

- Manifest explicitly says scrape. Fragile. Defer unless there's a strong reason.

### 🔴 §23.2a Argentina SNVS → `argentina-snvs`

- Boletín Integrado is a weekly bulletin (often PDF). Defer.

---

## Verification queue (before writing code)

These have **VERIFY** flags that need a live check:

1. **§5.4 Sentinelles** — confirm REST endpoint is live post-OData EOL, check schema.
2. **§6.3 InfoDengue / Mosqlimate** — confirm API auth + endpoint shape.
3. **§23.6a USDA APHIS HPAI** — check dashboard for hidden JSON/CSV endpoint.
4. **§23.1b Hong Kong CHP** — check for download links on dashboard pages.

I can WebFetch each of these in a single batch when you want — fast, low-context, gives us confident verdicts before we commit engineering time.

---

## What this triage explicitly does NOT do

- Verify that any URL still resolves (only the four flagged above).
- Inspect schema details (exact column names, dtypes, date format quirks).
- Test data download / parse end-to-end.

Those happen during ingest-module development, source-by-source. The triage's job is to set build order and flag anything that would derail us before we sink time into a source.
