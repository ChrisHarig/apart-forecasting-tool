"""Upload a source's parquet + rendered README to HuggingFace.

Re-ingest semantics:
  - Computes a deterministic data_hash of the normalized DataFrame.
  - Compares to the previous upload's data_hash (read from the live README).
  - If unchanged: skips the parquet upload entirely.
  - If changed: downloads the previous parquet, computes a row-level diff
    (added / removed / revised), and embeds the diff into the commit message.
  - README is uploaded separately when its rendered content differs (so
    curator edits to card.yaml flow through even when the data is static).

Run:
    python -m upload_pipeline.core.upload <source_id>

Env:
    HF_TOKEN — write-scoped HuggingFace token (loaded from .env)
"""
from __future__ import annotations

import os
import re
import sys
from pathlib import Path

import pandas as pd
import yaml
from dotenv import load_dotenv
from huggingface_hub import HfApi, create_repo, hf_hub_download
from huggingface_hub.utils import EntryNotFoundError, RepositoryNotFoundError

from upload_pipeline.core.render_card import render_card
from upload_pipeline.core.validate import REPO_ROOT, SOURCES_DIR, compute_diff, validate_source

CONFIG_PATH = REPO_ROOT / "upload_pipeline" / "config.yaml"


def _load_config() -> dict:
    return yaml.safe_load(CONFIG_PATH.read_text())


def _parse_frontmatter(readme: str) -> dict:
    """Pull the YAML frontmatter dict out of a README.md string."""
    if not readme.startswith("---"):
        return {}
    end_match = re.search(r"\n---\n", readme[3:])
    if not end_match:
        return {}
    yaml_text = readme[4 : 4 + end_match.start() - 1]
    try:
        return yaml.safe_load(yaml_text) or {}
    except yaml.YAMLError:
        return {}


def _data_hash_from_readme(readme: str) -> str | None:
    fm = _parse_frontmatter(readme)
    return (fm.get("computed") or {}).get("data_hash")


def _last_ingested_from_readme(readme: str) -> str | None:
    fm = _parse_frontmatter(readme)
    return (fm.get("computed") or {}).get("last_ingested")


def _try_download(repo_id: str, filename: str, token: str) -> Path | None:
    try:
        return Path(hf_hub_download(
            repo_id=repo_id, filename=filename,
            repo_type="dataset", token=token,
        ))
    except (EntryNotFoundError, RepositoryNotFoundError, FileNotFoundError):
        return None
    except Exception:
        return None


def _format_diff_summary(diff: dict, source_id: str) -> str:
    """Human-readable diff for commit messages."""
    if diff["added"] is None:
        return (f"Re-ingest {source_id} — "
                f"{diff['rows_prev']:,} → {diff['rows_new']:,} rows "
                f"(no row-key columns, fine-grained diff unavailable)")
    parts = []
    if diff["added"]:
        parts.append(f"+{diff['added']:,} new")
    if diff["revised"]:
        parts.append(f"{diff['revised']:,} revised")
    if diff["removed"]:
        parts.append(f"-{diff['removed']:,} removed")
    if not parts:
        parts.append("no row changes (column-level diff only)")
    return f"Re-ingest {source_id} — " + ", ".join(parts)


def upload_source(source_id: str) -> str:
    load_dotenv(REPO_ROOT / ".env")
    token = os.environ.get("HF_TOKEN")
    if not token:
        raise RuntimeError("HF_TOKEN not found in environment. Check .env file.")

    config = _load_config()
    repo_id = config["dataset_namespace_pattern"].format(source_id=source_id)

    source_dir = SOURCES_DIR / source_id
    parquet_path = source_dir / "data" / f"{source_id}.parquet"
    readme_path = source_dir / "README.md"

    if not parquet_path.exists():
        raise FileNotFoundError(f"Parquet not found: {parquet_path}")

    # Validate + compute (don't render yet; we may need to patch last_ingested).
    result = validate_source(source_id)
    if result["errors"]:
        raise ValueError(f"Validation failed for {source_id}; refusing to upload.")
    computed = result["computed"]
    new_data_hash = computed["data_hash"]

    api = HfApi(token=token)
    repo_existed = True
    try:
        api.repo_info(repo_id=repo_id, repo_type="dataset")
        print(f"\nRepo {repo_id} exists — checking for changes.")
    except RepositoryNotFoundError:
        repo_existed = False
        print(f"\nCreating public dataset repo {repo_id} ...")
        create_repo(
            repo_id=repo_id, repo_type="dataset",
            token=token, private=False, exist_ok=True,
        )

    prev_readme = None
    prev_data_hash = None
    prev_last_ingested = None
    if repo_existed:
        prev_readme_path = _try_download(repo_id, "README.md", token)
        if prev_readme_path:
            prev_readme = prev_readme_path.read_text()
            prev_data_hash = _data_hash_from_readme(prev_readme)
            prev_last_ingested = _last_ingested_from_readme(prev_readme)

    data_changed = new_data_hash != prev_data_hash

    # If data is unchanged, preserve the previous last_ingested timestamp.
    # Otherwise the README changes every run just because of the new clock,
    # which would mean a weekly cron writes a new commit every time.
    if not data_changed and prev_last_ingested:
        computed["last_ingested"] = prev_last_ingested

    new_readme_content = render_card(source_id, computed=computed)
    readme_path.write_text(new_readme_content)

    readme_changed = new_readme_content != prev_readme

    if not data_changed and not readme_changed:
        print(f"No change detected (data_hash {new_data_hash}). Skipping upload.")
        return f"https://huggingface.co/datasets/{repo_id}"

    diff_msg = ""
    if data_changed:
        if not repo_existed:
            diff_msg = f"Initial ingest — {source_id}"
        else:
            prev_parquet_path = _try_download(repo_id, f"data/{source_id}.parquet", token)
            if prev_parquet_path:
                prev_df = pd.read_parquet(prev_parquet_path)
                new_df = pd.read_parquet(parquet_path)
                diff = compute_diff(prev_df, new_df)
                diff_msg = _format_diff_summary(diff, source_id)
                print(f"  diff: {diff_msg}")
            else:
                diff_msg = f"Re-ingest {source_id} — previous parquet unavailable for diff"

    if readme_changed:
        readme_msg = (f"Update card ({source_id}) — data unchanged"
                      if not data_changed
                      else f"{diff_msg} — card update")
        print(f"Uploading README.md  [{readme_msg}]")
        api.upload_file(
            path_or_fileobj=str(readme_path),
            path_in_repo="README.md",
            repo_id=repo_id, repo_type="dataset",
            commit_message=readme_msg, token=token,
        )

    if data_changed:
        size_mb = parquet_path.stat().st_size / 1024 / 1024
        print(f"Uploading data/{parquet_path.name} ({size_mb:.2f} MB)  [{diff_msg}]")
        api.upload_file(
            path_or_fileobj=str(parquet_path),
            path_in_repo=f"data/{parquet_path.name}",
            repo_id=repo_id, repo_type="dataset",
            commit_message=diff_msg, token=token,
        )

    return f"https://huggingface.co/datasets/{repo_id}"


def main() -> int:
    if len(sys.argv) != 2:
        print("Usage: python -m upload_pipeline.core.upload <source_id>", file=sys.stderr)
        return 2
    source_id = sys.argv[1]
    print(f"Uploading {source_id} to HuggingFace ...")
    url = upload_source(source_id)
    print(f"\nDone: {url}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
