"""Verify EPI-Eval/<id>-predictions companion repos are set up correctly.

For each predictions sibling repo, checks:
  - The repo exists and is public.
  - It is not flagged disabled.
  - A README.md is present.
  - The discussions/PR API responds (i.e. PRs can be opened against it).
  - Any data files committed so far (count + first few names).

Read-only — does not modify any repos. Token is optional but useful: without
it, anonymous calls have low rate limits and may flake against 32 repos in a
row. With HF_TOKEN set you also see private metadata if a repo were ever
flipped private by accident.

Run:
    python -m upload_pipeline.core.verify_predictions_repos
    python -m upload_pipeline.core.verify_predictions_repos --only nhsn-hrd
"""
from __future__ import annotations

import argparse
import os
import sys
from dataclasses import dataclass

from dotenv import load_dotenv
from huggingface_hub import HfApi
from huggingface_hub.utils import (
    EntryNotFoundError,
    HfHubHTTPError,
    RepositoryNotFoundError,
)

from upload_pipeline.core.bootstrap_predictions_repos import (
    companion_repo_id,
    discover_source_ids,
)
from upload_pipeline.core.validate import SOURCES_DIR


@dataclass
class RepoCheck:
    source_id: str
    repo_id: str
    exists: bool
    public: bool | None
    disabled: bool | None
    has_readme: bool
    discussions_ok: bool
    file_count: int
    sample_files: list[str]
    error: str | None = None

    @property
    def healthy(self) -> bool:
        return (
            self.exists
            and self.public is True
            and self.disabled is False
            and self.has_readme
            and self.discussions_ok
            and self.error is None
        )


def check_repo(api: HfApi, source_id: str) -> RepoCheck:
    repo_id = companion_repo_id(source_id)
    try:
        info = api.repo_info(repo_id=repo_id, repo_type="dataset")
    except RepositoryNotFoundError:
        return RepoCheck(
            source_id=source_id, repo_id=repo_id, exists=False,
            public=None, disabled=None, has_readme=False, discussions_ok=False,
            file_count=0, sample_files=[],
            error="repo not found",
        )
    except HfHubHTTPError as e:
        return RepoCheck(
            source_id=source_id, repo_id=repo_id, exists=False,
            public=None, disabled=None, has_readme=False, discussions_ok=False,
            file_count=0, sample_files=[],
            error=f"repo_info: {e}",
        )

    public = not getattr(info, "private", False)
    disabled = bool(getattr(info, "disabled", False))

    try:
        files = list(api.list_repo_files(repo_id=repo_id, repo_type="dataset"))
    except EntryNotFoundError:
        files = []
    has_readme = "README.md" in files

    discussions_ok = True
    try:
        # Forcing the iterator to materialize triggers the API call.
        list(api.get_repo_discussions(repo_id=repo_id, repo_type="dataset"))
    except HfHubHTTPError as e:
        discussions_ok = False
        return RepoCheck(
            source_id=source_id, repo_id=repo_id, exists=True,
            public=public, disabled=disabled,
            has_readme=has_readme, discussions_ok=discussions_ok,
            file_count=len(files), sample_files=files[:3],
            error=f"discussions API: {e}",
        )

    data_files = [f for f in files if f.startswith("data/")]
    return RepoCheck(
        source_id=source_id, repo_id=repo_id, exists=True,
        public=public, disabled=disabled,
        has_readme=has_readme, discussions_ok=discussions_ok,
        file_count=len(data_files),
        sample_files=data_files[:3],
    )


def render_row(c: RepoCheck) -> str:
    if c.error and not c.exists:
        return f"  ✗ {c.repo_id:<55} MISSING  ({c.error})"
    flags = []
    flags.append("public" if c.public else "PRIVATE")
    if c.disabled:
        flags.append("DISABLED")
    flags.append("README ✓" if c.has_readme else "README ✗")
    flags.append("PRs ✓" if c.discussions_ok else "PRs ✗")
    files_label = (
        f"data: 0"
        if c.file_count == 0
        else f"data: {c.file_count} (e.g. {', '.join(c.sample_files)})"
    )
    icon = "✓" if c.healthy else "!"
    err_suffix = f"  [{c.error}]" if c.error else ""
    return f"  {icon} {c.repo_id:<55} {' · '.join(flags)} · {files_label}{err_suffix}"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--only", metavar="SOURCE_ID",
                        help="Only verify this one source.")
    args = parser.parse_args()

    load_dotenv()
    token = os.environ.get("HF_TOKEN")
    api = HfApi(token=token) if token else HfApi()

    if args.only:
        if not (SOURCES_DIR / args.only / "card.yaml").exists():
            print(f"ERROR: source {args.only!r} not found.", file=sys.stderr)
            return 2
        source_ids = [args.only]
    else:
        source_ids = discover_source_ids()

    print(f"Verifying {len(source_ids)} predictions companion repo(s)"
          f"{' (anonymous — slower)' if not token else ''}\n")

    results: list[RepoCheck] = []
    for sid in source_ids:
        c = check_repo(api, sid)
        print(render_row(c))
        results.append(c)

    healthy = sum(1 for c in results if c.healthy)
    bad = len(results) - healthy
    print()
    print(f"Summary: {healthy} healthy, {bad} need attention.")
    return 0 if bad == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
