"""Generate fake multi-team predictions and push them to a companion repo.

Used to dogfood the v2.5 read-side overlay before any real forecasters
have submitted. Generates synthetic forecasts from a handful of "team"
personas with different bias / spread profiles so the overlay UI has
something contrastable to render. Idempotent: each persona writes to a
fixed filename (`data/<submitter>-synth.parquet`), so re-running just
overwrites that persona's slice rather than spawning duplicates.

Schema matches `src/data/predictions/parquet.ts` exactly so the read-side
treats seeded and browser-submitted predictions uniformly.

Run:
    python -m upload_pipeline.core.seed_synth_predictions                            # nhsn-hrd default
    python -m upload_pipeline.core.seed_synth_predictions --target nhsn-hrd \\
        --column totalconfflunewadm --location 06 --location-name CA
    python -m upload_pipeline.core.seed_synth_predictions --dry-run

Env:
    HF_TOKEN — write-scoped HuggingFace token (loaded from .env), required
               unless --dry-run.
"""
from __future__ import annotations

import argparse
import io
import os
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
from dotenv import load_dotenv
from huggingface_hub import HfApi
from huggingface_hub.utils import RepositoryNotFoundError

from upload_pipeline.core.bootstrap_predictions_repos import companion_repo_id
from upload_pipeline.core.validate import REPO_ROOT, SOURCES_DIR

QUANTILES = [0.025, 0.10, 0.25, 0.50, 0.75, 0.90, 0.975]
SCHEMA_VERSION = 1


@dataclass
class Persona:
    submitter: str
    model_name: str
    description: str
    bias: float        # multiplier on truth (1.0 = unbiased)
    point_noise: float # gaussian σ on point estimate, fraction of truth
    spread: float      # half-width of 80% interval as fraction of point
    seed: int          # deterministic per-persona


# Four personas chosen to be visually distinct on the overlay.
PERSONAS: list[Persona] = [
    Persona(
        submitter="team-baseline",
        model_name="naive-last-value",
        description="Carries last observed value forward. Tight quantile bands.",
        bias=1.0, point_noise=0.05, spread=0.10, seed=1,
    ),
    Persona(
        submitter="team-arima",
        model_name="arima-001",
        description="Decent forecaster — small bias, moderate intervals.",
        bias=1.05, point_noise=0.12, spread=0.25, seed=2,
    ),
    Persona(
        submitter="team-overshoot",
        model_name="alarmist-v1",
        description="Consistently over-predicts by ~40%.",
        bias=1.40, point_noise=0.15, spread=0.30, seed=3,
    ),
    Persona(
        submitter="team-undershoot",
        model_name="cautious-v1",
        description="Consistently under-predicts by ~45%.",
        bias=0.55, point_noise=0.10, spread=0.20, seed=4,
    ),
]


def load_truth_slice(
    target: str, column: str, location: str, n_recent: int
) -> pd.DataFrame:
    parquet_path = SOURCES_DIR / target / "data" / f"{target}.parquet"
    if not parquet_path.exists():
        raise FileNotFoundError(f"Local truth parquet missing: {parquet_path}")
    df = pd.read_parquet(parquet_path)
    if "location_id" not in df.columns:
        raise ValueError(f"{target} has no location_id column — pick another target.")
    if column not in df.columns:
        raise ValueError(
            f"{target} has no column {column!r}. Available numeric columns: "
            f"{[c for c in df.columns if pd.api.types.is_numeric_dtype(df[c])]}"
        )
    sub = df[df["location_id"] == location].copy()
    if sub.empty:
        raise ValueError(f"No rows for location_id={location!r} in {target}.")
    sub = sub.dropna(subset=[column]).sort_values("date").tail(n_recent).reset_index(drop=True)
    if len(sub) == 0:
        raise ValueError(
            f"location_id={location!r} has no non-null {column} rows."
        )
    return sub[["date", column]].rename(columns={column: "truth"})


def synth_persona_rows(
    persona: Persona,
    truth: pd.DataFrame,
    target: str,
    column: str,
    location_name: str,
    submitted_at: str,
    horizon_extra_weeks: int,
) -> list[dict]:
    rng = np.random.default_rng(persona.seed)
    rows: list[dict] = []

    in_coverage = list(zip(truth["date"], truth["truth"]))
    # Synthesize forecast-horizon dates (past truth's last date) by extending
    # the most recent truth value forward by week. The "truth" for those
    # rows is the trailing observed value — we generate predictions only,
    # there's intentionally no truth to score against past coverage.
    last_date = pd.Timestamp(truth["date"].iloc[-1])
    last_truth = float(truth["truth"].iloc[-1])
    horizon_dates = [
        last_date + pd.Timedelta(weeks=k) for k in range(1, horizon_extra_weeks + 1)
    ]
    horizon = [(d, last_truth) for d in horizon_dates]

    for date, truth_val in in_coverage + horizon:
        date_str = pd.Timestamp(date).strftime("%Y-%m-%d")
        # Point estimate: bias × truth + gaussian noise
        point = persona.bias * truth_val * (1 + rng.normal(0, persona.point_noise))
        point = max(point, 0.0)  # admissions floor at zero

        # Build a quantile pyramid centered on `point` whose 80% interval
        # half-width matches `persona.spread`. Other quantiles fan out
        # roughly proportionally — not statistically rigorous, just visually
        # plausible bands for the overlay UI.
        half_80 = persona.spread * point
        # σ implied by the 80% interval (z=1.282 for 0.9 quantile)
        sigma = half_80 / 1.282
        for q in QUANTILES:
            from scipy.stats import norm
            z = norm.ppf(q)
            v = max(point + z * sigma, 0.0)
            rows.append({
                "target_date": date_str,
                "target_dataset": target,
                "target_column": column,
                "submitter": persona.submitter,
                "model_name": persona.model_name,
                "description": persona.description,
                "quantile": q,
                "value": float(v),
                "submitted_at": submitted_at,
                "location": location_name,
            })
        # Point estimate as a separate row (quantile=null), per schema.
        rows.append({
            "target_date": date_str,
            "target_dataset": target,
            "target_column": column,
            "submitter": persona.submitter,
            "model_name": persona.model_name,
            "description": persona.description,
            "quantile": None,
            "value": float(point),
            "submitted_at": submitted_at,
            "location": location_name,
        })

    return rows


def rows_to_parquet_bytes(rows: list[dict], persona: Persona, target: str, column: str) -> bytes:
    df = pd.DataFrame(rows)
    schema = pa.schema([
        ("target_date", pa.string()),
        ("target_dataset", pa.string()),
        ("target_column", pa.string()),
        ("submitter", pa.string()),
        ("model_name", pa.string()),
        ("description", pa.string()),
        ("quantile", pa.float64()),
        ("value", pa.float64()),
        ("submitted_at", pa.string()),
        ("location", pa.string()),
    ])
    table = pa.Table.from_pandas(df, schema=schema, preserve_index=False)
    # Mirror the kvMetadata that the browser-side parquet writer embeds.
    metadata = {
        b"epi-eval.schema_version": str(SCHEMA_VERSION).encode(),
        b"epi-eval.target_dataset": target.encode(),
        b"epi-eval.target_column": column.encode(),
        b"epi-eval.submitter": persona.submitter.encode(),
        b"epi-eval.model_name": persona.model_name.encode(),
        b"epi-eval.synthetic": b"1",  # tag so a maintainer can spot fakes
    }
    table = table.replace_schema_metadata(metadata)
    buf = io.BytesIO()
    pq.write_table(table, buf, compression="snappy")
    return buf.getvalue()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--target", default="nhsn-hrd")
    parser.add_argument("--column", default="totalconfflunewadm")
    parser.add_argument("--location", default="06",
                        help="location_id from the truth parquet (FIPS for US states).")
    parser.add_argument("--location-name", default="CA",
                        help="Pretty label written into the `location` column.")
    parser.add_argument("--n-recent", type=int, default=16,
                        help="How many recent truth weeks to overlay forecasts on.")
    parser.add_argument("--horizon-weeks", type=int, default=4,
                        help="How many weeks past truth coverage to forecast.")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    truth = load_truth_slice(
        args.target, args.column, args.location, args.n_recent
    )
    print(f"Truth: {args.target} / {args.column} / loc={args.location} ({args.location_name})")
    print(f"  {len(truth)} weeks, {truth['date'].min().date()} → {truth['date'].max().date()}")
    print(f"  +{args.horizon_weeks} forecast-horizon weeks past coverage\n")

    submitted_at = datetime.now(tz=timezone.utc).isoformat()
    repo_id = companion_repo_id(args.target)

    if args.dry_run:
        for persona in PERSONAS:
            rows = synth_persona_rows(
                persona, truth, args.target, args.column,
                args.location_name, submitted_at, args.horizon_weeks,
            )
            print(f"  [{persona.submitter}] would write {len(rows)} rows "
                  f"→ data/{persona.submitter}-synth.parquet")
        print(f"\nDry-run only. Re-run without --dry-run to push to {repo_id}.")
        return 0

    load_dotenv(REPO_ROOT / ".env")
    token = os.environ.get("HF_TOKEN")
    if not token:
        print("ERROR: HF_TOKEN not found in environment (.env).", file=sys.stderr)
        return 2

    api = HfApi(token=token)
    try:
        api.repo_info(repo_id=repo_id, repo_type="dataset")
    except RepositoryNotFoundError:
        print(f"ERROR: companion repo {repo_id} doesn't exist. Run "
              f"bootstrap_predictions_repos --apply --only {args.target} first.",
              file=sys.stderr)
        return 2

    for persona in PERSONAS:
        rows = synth_persona_rows(
            persona, truth, args.target, args.column,
            args.location_name, submitted_at, args.horizon_weeks,
        )
        parquet_bytes = rows_to_parquet_bytes(rows, persona, args.target, args.column)
        path_in_repo = f"data/{persona.submitter}-synth.parquet"
        size_kb = len(parquet_bytes) / 1024
        print(f"  Uploading {path_in_repo} ({size_kb:.1f} KB, {len(rows)} rows)…")
        api.upload_file(
            path_or_fileobj=parquet_bytes,
            path_in_repo=path_in_repo,
            repo_id=repo_id, repo_type="dataset",
            commit_message=f"Synth predictions: {persona.submitter} ({persona.model_name})",
            token=token,
        )

    print(f"\nDone. {len(PERSONAS)} personas uploaded to {repo_id}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
