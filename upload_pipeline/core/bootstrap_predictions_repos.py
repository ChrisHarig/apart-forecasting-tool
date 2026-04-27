"""Create EPI-Eval/<source_id>-predictions sibling datasets on HuggingFace.

Each EPI-Eval truth dataset gets a companion repo that accumulates community-
submitted forecasts in long format. This script bootstraps those companion
repos so the dashboard's "Submit to HuggingFace" flow has somewhere to PR.
The submission flow itself is in src/data/predictions/hf-submit.ts.

Idempotent — safe to re-run; existing repos are skipped. By default the script
runs in --dry-run mode and prints what *would* happen; pass --apply to actually
create repos and upload READMEs.

Run:
    python -m upload_pipeline.core.bootstrap_predictions_repos                  # dry-run
    python -m upload_pipeline.core.bootstrap_predictions_repos --apply
    python -m upload_pipeline.core.bootstrap_predictions_repos --apply --only nhsn-hrd
    python -m upload_pipeline.core.bootstrap_predictions_repos --apply --refresh-readme

Env:
    HF_TOKEN — write-scoped HuggingFace token (loaded from .env)
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

import yaml
from dotenv import load_dotenv
from huggingface_hub import HfApi, create_repo
from huggingface_hub.utils import RepositoryNotFoundError

from upload_pipeline.core.validate import REPO_ROOT, SOURCES_DIR

PREDICTIONS_SUFFIX = "-predictions"
ORG = "EPI-Eval"
SCHEMA_VERSION = 1


def companion_repo_id(source_id: str) -> str:
    return f"{ORG}/{source_id}{PREDICTIONS_SUFFIX}"


def truth_repo_id(source_id: str) -> str:
    return f"{ORG}/{source_id}"


def discover_source_ids() -> list[str]:
    """All source IDs that have a card.yaml under upload_pipeline/sources/."""
    ids: list[str] = []
    for child in sorted(SOURCES_DIR.iterdir()):
        if child.is_dir() and (child / "card.yaml").exists():
            ids.append(child.name)
    return ids


def load_card(source_id: str) -> dict:
    return yaml.safe_load((SOURCES_DIR / source_id / "card.yaml").read_text()) or {}


def render_companion_readme(source_id: str, card: dict) -> str:
    """Minimal but useful starter README for a predictions companion repo."""
    pretty = card.get("pretty_name", source_id)
    truth_id = truth_repo_id(source_id)
    value_cols = card.get("value_columns") or []
    value_lines = "\n".join(
        f"- `{c.get('name')}`" + (f" ({c['unit']})" if c.get("unit") else "")
        for c in value_cols
        if c.get("name")
    ) or "_(see truth dataset for the column list)_"

    frontmatter = {
        "pretty_name": f"Predictions — {pretty}",
        "license": "other",
        "tags": [
            "epi-eval",
            "predictions",
            "forecast-evaluation",
            f"companion-of-{source_id}",
        ],
        "configs": [
            {
                "config_name": "default",
                "data_files": [{"split": "train", "path": "data/*.parquet"}],
            }
        ],
    }
    fm = yaml.safe_dump(frontmatter, sort_keys=False).strip()

    body = f"""# Predictions for {pretty}

Community-submitted forecasts targeting [`{truth_id}`](https://huggingface.co/datasets/{truth_id}).
Each row is one quantile (or point) forecast for one target date — see the
schema below.

This repo accumulates accepted submissions from many forecasters. New
predictions arrive as community pull requests opened from the [EPI-Eval
dashboard](https://github.com/ChrisHarig/apart-forecasting-tool); a
maintainer reviews each PR before merging.

## Schema (v{SCHEMA_VERSION})

| column | type | notes |
| --- | --- | --- |
| `target_date` | string (`YYYY-MM-DD`) | The date being forecast |
| `target_dataset` | string | Always `{source_id}` |
| `target_column` | string | Truth column being forecast (see below) |
| `submitter` | string | Forecaster name or HF username |
| `model_name` | string | Identifier for the model run |
| `description` | string | Free-form notes on the model |
| `quantile` | float (nullable) | In `[0, 1]`. `null` = point estimate |
| `value` | float | Forecast value (in the truth column's units) |
| `submitted_at` | string (ISO 8601) | UTC submission timestamp |
| _(pass-through dims)_ | string | Categorical dims from the source CSV |

Long format: one row per `(target_date, [dim values…], quantile)`. A
forecaster providing the median plus 50%/80%/95% intervals emits 7 rows per
date (one point + 6 quantiles). Multiple submissions from the same forecaster
land as separate parquet files under `data/`.

## Forecast targets

Truth columns from `{truth_id}` you can forecast:

{value_lines}

## Submitting

The dashboard at [apart-forecasting-tool](https://github.com/ChrisHarig/apart-forecasting-tool)
handles the full submission flow: drag-drop a CSV, pick this dataset as the
"Compare to" target, review your scores against the truth, and click "Submit
to HuggingFace." The dashboard serializes your CSV into the schema above and
opens a community PR here.

## Notes

- Predictions whose `target_date` falls outside the truth dataset's coverage
  (forecast horizon) are still accepted. Comparison metrics on the dashboard
  compute only on the dates where truth is available.
- A submission's `submitter` value is its only identity claim — there's no
  signed authentication. Reviewers should sanity-check unfamiliar submitters.

_Initialized by `upload_pipeline.core.bootstrap_predictions_repos`._
"""
    return f"---\n{fm}\n---\n\n{body}"


def repo_exists(api: HfApi, repo_id: str) -> bool:
    try:
        api.repo_info(repo_id=repo_id, repo_type="dataset")
        return True
    except RepositoryNotFoundError:
        return False


def bootstrap_one(
    api: HfApi,
    token: str,
    source_id: str,
    apply: bool,
    refresh_readme: bool,
) -> str:
    repo_id = companion_repo_id(source_id)
    card = load_card(source_id)
    exists = repo_exists(api, repo_id)

    if not exists:
        if not apply:
            return f"WOULD CREATE  {repo_id}"
        create_repo(
            repo_id=repo_id, repo_type="dataset",
            token=token, private=False, exist_ok=True,
        )
        readme = render_companion_readme(source_id, card)
        api.upload_file(
            path_or_fileobj=readme.encode("utf-8"),
            path_in_repo="README.md",
            repo_id=repo_id, repo_type="dataset",
            commit_message=f"Initialize predictions companion for {source_id}",
            token=token,
        )
        return f"CREATED       {repo_id}"

    if refresh_readme:
        if not apply:
            return f"WOULD REFRESH {repo_id} (README)"
        readme = render_companion_readme(source_id, card)
        api.upload_file(
            path_or_fileobj=readme.encode("utf-8"),
            path_in_repo="README.md",
            repo_id=repo_id, repo_type="dataset",
            commit_message=f"Refresh README for {source_id} predictions companion",
            token=token,
        )
        return f"REFRESHED     {repo_id}"

    return f"OK            {repo_id} (exists)"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true",
                        help="Actually create repos. Without this flag, runs as a dry-run.")
    parser.add_argument("--only", metavar="SOURCE_ID",
                        help="Only bootstrap this one source.")
    parser.add_argument("--refresh-readme", action="store_true",
                        help="If a companion repo exists, re-upload its README.")
    args = parser.parse_args()

    load_dotenv(REPO_ROOT / ".env")
    token = os.environ.get("HF_TOKEN")
    if not token:
        # Allow dry-run without a token; only fail when actually applying.
        if args.apply:
            print("ERROR: HF_TOKEN not found in environment (.env). "
                  "Required for --apply.", file=sys.stderr)
            return 2
        token = ""

    api = HfApi(token=token) if token else HfApi()

    if args.only:
        source_ids = [args.only]
        if not (SOURCES_DIR / args.only / "card.yaml").exists():
            print(f"ERROR: source {args.only!r} not found in {SOURCES_DIR}",
                  file=sys.stderr)
            return 2
    else:
        source_ids = discover_source_ids()

    mode = "APPLY" if args.apply else "DRY-RUN"
    print(f"[{mode}] {len(source_ids)} source(s) to process\n")

    created = refreshed = existed = 0
    failures: list[tuple[str, Exception]] = []
    for sid in source_ids:
        try:
            line = bootstrap_one(api, token, sid, args.apply, args.refresh_readme)
            print(f"  {line}")
            if line.startswith("CREATED") or line.startswith("WOULD CREATE"):
                created += 1
            elif line.startswith("REFRESHED") or line.startswith("WOULD REFRESH"):
                refreshed += 1
            else:
                existed += 1
        except Exception as e:  # noqa: BLE001  — surface any HF error per-source
            failures.append((sid, e))
            print(f"  FAILED        {companion_repo_id(sid)}  ({e.__class__.__name__}: {e})")

    print()
    print(f"Summary: {created} new, {refreshed} README-refreshed, "
          f"{existed} already existed, {len(failures)} failed.")
    if not args.apply:
        print("\nDry-run only. Re-run with --apply to actually create repos.")
    if failures:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
