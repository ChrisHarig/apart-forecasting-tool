# ChatGPT Handoff README Pack

This folder contains the project context and next-step material to give ChatGPT when asking it to create detailed Codex prompts for Sentinel Atlas.

## Suggested Upload Order

1. `01_PROJECT_README.md`
2. `02_DEVELOPER_README.md`
3. `07_VERIFICATION_REPORT.md`
4. `06_NEXT_CODEX_PROMPT_TASKS.md`
5. Add backend docs only when the prompt needs backend/API work:
   - `03_BACKEND_README.md`
   - `04_BACKEND_ARCHITECTURE.md`
   - `05_FRONTEND_BACKEND_CONTRACT.md`

## What To Ask ChatGPT

Use this request:

```text
Use these Sentinel Atlas handoff docs to create detailed, standalone Codex prompts.
Each prompt should be scoped to one task, include exact files/areas to inspect,
preserve aggregate-only safety constraints, avoid fabricated public-health data,
and include acceptance criteria plus commands Codex should run.
Start with the tasks in 06_NEXT_CODEX_PROMPT_TASKS.md.
```

## Key Product Constraints

- Country-first public-health data aggregation app.
- Large interactive world map is the World Dashboard focal point.
- Country selection happens by map click, not a dropdown.
- Clicking a country updates selected country in place and does not change the current view.
- Primary navigation remains exactly:
  - World Dashboard
  - Sources
  - Time Series
- No fake pandemic predictions, fake risk scores, fake Rt/R0, synthetic scenario mode, or fabricated time-series data.
- Empty states are preferred when real/user-uploaded data is unavailable.
- Time Series source and metric options should come from actual local/uploaded records, not fabricated values or registry metadata alone.
- User-added sources must be labeled user-added or unvalidated.
- Aggregate-only data. Reject or warn against PII, individual medical records, individual-level tracking, and precise personal mobility traces.
- Frontend should run without a backend, even though a backend scaffold exists.
