# Sentinel Atlas Next Codex Prompt Tasks

Use this file as source material for ChatGPT to create detailed, standalone Codex prompts. Each generated prompt should tell Codex to inspect the repo first, keep changes scoped, run relevant tests/builds, avoid fabricated public-health data, and report exact commands/results.

## Current Baseline

- Frontend: Vite, React, TypeScript, MapLibre GL, localStorage-only user sources and uploaded datasets.
- Backend: FastAPI scaffold exists, but frontend must still run without it.
- Verified frontend commands pass:
  - `npm test` via bundled npm: 9 test files, 35 tests passed.
  - `npm run build` via bundled npm: build passed with a large chunk warning.
- Verified backend command passes:
  - `python -m pytest` in `backend/`: 11 tests passed.
- Preview URL used during verification:
  - `http://localhost:4174/`
- Known limitation from verification:
  - The in-app browser runtime was blocked by `Access is denied`, so manual click/zoom/pan browser verification was partial.

## Global Constraints For Every Prompt

- Do not reintroduce synthetic pandemic simulations, fake risk scores, fake Rt/R0, fake outbreak forecasts, or fake data overlays.
- Do not add a country selector dropdown.
- Keep the primary navigation to exactly:
  - World Dashboard
  - Sources
  - Time Series
- Preserve aggregate-only safety language.
- Reject or warn against PII, individual medical records, individual-level tracking, and precise personal mobility traces.
- Prefer clean empty states over placeholder/fabricated data.
- Do not introduce a required backend dependency for the frontend.

## Task 1: Add Runtime Browser Smoke Coverage

Goal: Add automated runtime coverage for the main user journey so map and navigation regressions are caught.

Suggested scope:
- Add Playwright or another lightweight browser test setup if appropriate.
- Test that the app loads to World Dashboard.
- Test side navigation has exactly three items.
- Test no country selector dropdown is rendered.
- Test removed simulator terms are absent from visible UI.
- Test the map container is present and large enough to be the page focal point.
- Test reset-view control exists.
- Test that United States is selected by default.
- If feasible, test map hover/click selection with MapLibre events and confirm selection changes without navigation. If not feasible, document the limitation and test the nearest stable state contract.

Acceptance criteria:
- A single command runs the browser smoke tests.
- The test is fast enough for CI.
- `npm test` and `npm run build` still pass.
- The prompt should ask Codex to update README/CI only if a new command is introduced.

## Task 2: Reduce Frontend Bundle Size

Goal: Address the Vite warning that the main JS bundle is over 500 kB after minification.

Suggested scope:
- Inspect current bundle composition.
- Lazy-load view-level components where practical.
- Consider splitting MapLibre/world-atlas and Recharts into separate chunks.
- Keep user-perceived first screen stable.
- Do not change app behavior or data semantics.

Acceptance criteria:
- `npm run build` passes.
- Bundle warning is eliminated or meaningfully reduced with clear before/after sizes.
- No visual or navigation regressions.
- If warning remains, document why and what remains heavy.

## Task 3: Frontend Backend Adapter Contracts

Goal: Make future backend integration cleaner while preserving frontend-only operation.

Suggested scope:
- Add typed frontend API contracts/adapters for:
  - source registry
  - country source availability
  - time-series records
  - country news summaries
- Keep local catalog/localStorage as default fallback.
- Use environment-controlled backend base URL if needed.
- Do not require a backend process to run the frontend.
- Do not scrape from the frontend.

Acceptance criteria:
- Adapter functions are typed and tested.
- Offline/local fallback behavior is explicit and covered by tests.
- Failed backend calls show clean empty/error states, not fake data.
- `npm test` and `npm run build` pass.

## Task 4: Add Source Workflow UI Tests

Goal: Cover the user-added source workflow at the UI level, not only adapter level.

Suggested scope:
- Add tests for opening the Add source modal.
- Validate required fields.
- Validate sensitive terms are rejected.
- Save a valid aggregate source.
- Confirm saved source is labeled user-added or not validated.
- Confirm persistence through localStorage or equivalent reload simulation.

Acceptance criteria:
- Tests cover both success and validation failure.
- User-added source appears only under the selected country coverage.
- No backend is required.
- `npm test` and `npm run build` pass.

## Task 5: Time Series Upload UI Tests

Goal: Cover uploaded CSV/JSON behavior from the UI layer.

Suggested scope:
- Test default USA selected-country no-data empty state.
- Test valid CSV upload renders a chart/table for the selected country.
- Test records for another country are filtered out.
- Test source and metric controls are derived only from uploaded/local records.
- Test invalid CSV/JSON displays validation errors.
- Test PII-like fields are rejected.
- Test all required date range presets:
  - 2 weeks
  - 1 month
  - 3 months
  - 6 months
  - 1 year
  - 2 years

Acceptance criteria:
- No generated values are used to fill gaps.
- Uploaded records normalize to the target schema.
- `npm test` and `npm run build` pass.

## Task 6: Country Hover News Adapter UX

Goal: Improve future news/scraper integration without inventing news or adding permanent map overlays.

Suggested scope:
- Review current hover-country and news-summary flow.
- Add loading/error/empty display states in a non-obstructive panel outside the main map canvas if news UI is reintroduced.
- Add tests for no-news-backend empty state.
- Make it clear the frontend does not scrape.
- Keep any future news/status panel compact and outside the map so the map remains focused.

Acceptance criteria:
- No permanent instructional, hover, or fake-news cards obstruct the map.
- No hardcoded fake headlines are introduced.
- Adapter can later point to `/api/countries/:iso3/news/latest`.
- `npm test` and `npm run build` pass.

## Task 7: Backend API Contract Alignment

Goal: Ensure backend route contracts match the frontend target data model and future adapter expectations.

Suggested scope:
- Compare backend docs and schemas with frontend types.
- Align naming where practical without broad churn.
- Ensure source categories match frontend categories.
- Ensure time-series upload/response can represent:
  - sourceId
  - countryIso3
  - date
  - metric
  - value
  - unit
  - locationName
  - latitude
  - longitude
  - admin1/admin2
  - provenance
  - notes
- Keep backend aggregate-only validation strict.

Acceptance criteria:
- Backend tests cover schema compatibility.
- Frontend contracts can consume backend responses without ad hoc mapping.
- `python -m pytest` passes in `backend/`.
- Frontend tests/build still pass if shared docs/types are touched.

## Task 8: README And Developer Handoff Cleanup

Goal: Make documentation concise, accurate, and implementation-ready after the pivot.

Suggested scope:
- Remove stale MVP or legacy simulator wording from documentation unless explicitly framed as removed history.
- Document current frontend-only operation plus optional backend scaffold.
- Document how to run:
  - frontend tests
  - frontend build
  - preview/dev server
  - backend tests
- Document known limitations and data-integrity constraints.
- Add a short "How to verify before PR" checklist.

Acceptance criteria:
- README reflects current product behavior.
- No confusing "No backend" wording when referring to the repo as a whole.
- Documentation clearly says no live data pipeline and no fabricated data.
- Commands in docs are accurate for a normal Node/Python environment.

## Task 9: Map Fallback And Offline Verification

Goal: Make map behavior reliable when external basemap tiles are unavailable.

Suggested scope:
- Verify fallback style renders local country boundaries.
- Add tests or a manual verification script for fallback behavior.
- Ensure fallback behavior is silent or uses a non-obstructive status outside the map.
- Keep country click/hover layers available when style falls back.

Acceptance criteria:
- Country boundaries remain visible without basemap tiles.
- Selection and hover still work with fallback style.
- No network dependency is required for basic country selection.
- `npm test` and `npm run build` pass.

## Task 10: CI Workflow Expansion

Goal: Make CI catch the same regressions found during verification.

Suggested scope:
- Keep existing GitHub Pages deployment workflow intact.
- Add any new frontend test commands introduced by prior tasks.
- Consider backend pytest workflow if backend is now part of the repo deliverable.
- Cache dependencies appropriately.
- Avoid making deployment depend on optional backend services.

Acceptance criteria:
- CI runs frontend tests and build.
- If backend tests are added to CI, they run without external DB services by using SQLite/default config.
- GitHub Pages deployment still uploads `dist/`.
