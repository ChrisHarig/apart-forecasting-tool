# Backend Architecture Note

Sentinel Atlas is organized around uneven country data availability. The backend stores data source metadata, source-country coverage, aggregate observations, locations, event/news signals, quality reports, feature availability, and model-run explanations separately so the frontend and model layer can see exactly which signals exist for each country.

## First-Pass Design

- FastAPI exposes a typed API and OpenAPI docs.
- SQLite is the local fallback so the backend starts without a heavyweight database.
- SQLAlchemy models are written so Postgres can replace SQLite through `SENTINEL_DATABASE_URL`.
- Geospatial fields use lat/lon and JSON in the fallback schema. PostGIS TODOs are marked in `app/db/models.py`.
- Connector placeholders describe sources and limitations but never fabricate observations.
- Uploaded aggregate data is normalized into a canonical observation table.
- Readiness services compute transparent heuristic scores.
- Model eligibility selects only supported models and returns `insufficient_data` by default.
- Forecast benchmark services now create reproducible benchmark dataset snapshots before scoring. Built-in baselines, optional whitelisted StatsForecast AutoETS, and uploaded prediction CSV sets are evaluated against the same stored aggregate train/test split, holdout dates, observed values, and scoring rules. Uploaded model support remains prediction CSV only; the backend does not execute uploaded model code.
- Forecast challenge snapshots support Sprint A retrospective holdouts and prospective challenges. Retrospective snapshots freeze historical train/holdout windows; prospective snapshots freeze the train window at a cutoff and generate future target dates without fabricating truth values.
- Sprint B stores successful built-in challenge forecasts as canonical `PredictionSet` / `PredictionPoint` rows. Built-ins use the challenge snapshot's frozen train rows and exact target dates, persist as `prediction_source: built_in` / `submission_track: internal_baseline`, and return per-model `complete`, `insufficient_data`, `model_unavailable`, or `failed` statuses without failing the full challenge run.
- Sprint C adds challenge-tied user prediction CSV upload, persisted `ForecastScore` records, scoring for retrospective and prospective challenges when aggregate truth exists, leaderboard ranking by SMAPE/RMSE/MAE, and dynamic observed-vs-predicted comparison points. Unit or metric mismatches can be stored as overlay-only data when allowed, but overlay-only predictions are not scored or ranked.
- Sprint D adds lightweight hackathon submitter metadata, public/verified/internal submission tracks, review decisions, privacy-preserving submitter list responses, and leaderboard filters by track, review status, and unreviewed inclusion. This is metadata labeling only and does not add authentication or executable model uploads.

## Upgrade Path

1. Add Alembic migrations for the current tables.
2. Enable PostGIS geometry columns for countries and locations.
3. Add GiST indexes for country geometry and point locations.
4. Add TimescaleDB hypertables for `observations` and `model_output_points` if supported.
5. Implement live adapters one at a time, each with source terms, rate limits, and provenance.
6. Promote data quality scoring rules into versioned policies.
7. Add authenticated model/prediction ownership, benchmark access controls, and stricter production model registry governance.
8. Decide whether optional `statsforecast` should remain an extra or become part of the production backend image.
9. Add a blind benchmark workflow if the product needs stronger guarantees that external models did not train on holdout values.
10. Add a challenge lifecycle job to rescore prospective challenges automatically when new aggregate truth observations arrive.

## Safety Boundary

The backend supports aggregate public-health readiness analysis only. It must reject individual identifiers, medical records, personal traces, executable model uploads, and any request to generate pathogen engineering, wet-lab, evasion, dissemination, or operational outbreak-action guidance.
