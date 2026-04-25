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

## Upgrade Path

1. Add Alembic migrations for the current tables.
2. Enable PostGIS geometry columns for countries and locations.
3. Add GiST indexes for country geometry and point locations.
4. Add TimescaleDB hypertables for `observations` and `model_output_points` if supported.
5. Implement live adapters one at a time, each with source terms, rate limits, and provenance.
6. Promote data quality scoring rules into versioned policies.

## Safety Boundary

The backend supports aggregate public-health readiness analysis only. It must reject individual identifiers, medical records, personal traces, and any request to generate pathogen engineering, wet-lab, evasion, dissemination, or operational outbreak-action guidance.

