"""Render a source's HF dataset card README.md.

Calls the validator (which also computes the `computed:` block), merges
curated + computed into the YAML frontmatter, and emits a prose body
that summarizes coverage, columns, and caveats for human readers.

Run:
    python -m upload_pipeline.core.render_card <source_id>
"""
from __future__ import annotations

import sys
from pathlib import Path

import yaml

from upload_pipeline.core.validate import REPO_ROOT, SOURCES_DIR, validate_source


def _value_columns_table(value_columns: list[dict]) -> str:
    rows = [
        "| Column | Unit | value_type | Aggregation | Description |",
        "|--------|------|------------|-------------|-------------|",
    ]
    for vc in value_columns:
        rows.append(
            f"| `{vc['name']}` | {vc.get('unit', '')} | "
            f"`{vc.get('value_type', '')}` | "
            f"`{vc.get('aggregation', '')}` | "
            f"{vc.get('description', '')} |"
        )
    return "\n".join(rows)


def _bullet_list(items: list[str]) -> str:
    return "\n".join(f"- {it}" for it in items)


def _format_time_coverage(intervals: list[dict]) -> str:
    return "; ".join(f"{iv['start']} → {iv['end']}" for iv in intervals)


def _format_relations(card: dict) -> list[str]:
    out = []
    if card.get("gold_standard_for"):
        out.append(
            "**Gold standard for:** "
            + ", ".join(f"`{x}`" for x in card["gold_standard_for"])
        )
    if card.get("succeeds"):
        out.append(f"**Succeeds:** `{card['succeeds']}` (different reporting program; "
                   f"do not splice rows directly without normalization)")
    if card.get("vintaged_version_of"):
        out.append(f"**Vintaged version of:** `{card['vintaged_version_of']}`")
    if card.get("derived_from"):
        out.append(
            "**Derived from:** "
            + ", ".join(f"`{x}`" for x in card["derived_from"])
        )
    return out


def render_card(source_id: str, computed: dict | None = None) -> str:
    """Render a source's README.md.

    If `computed` is supplied, uses it directly (skips re-validation). This
    lets the caller patch fields like `last_ingested` between validation
    and rendering — used by the uploader to preserve timestamps when the
    data hasn't actually changed.
    """
    if computed is None:
        result = validate_source(source_id)
        if result["errors"]:
            raise ValueError(
                f"Cannot render card for {source_id!r}: validation failed with "
                f"{len(result['errors'])} error(s). See output above."
            )
        computed = result["computed"]

    source_dir = SOURCES_DIR / source_id
    card = yaml.safe_load((source_dir / "card.yaml").read_text())

    merged = dict(card)
    merged["computed"] = computed

    frontmatter = yaml.safe_dump(
        merged,
        sort_keys=False,
        default_flow_style=False,
        width=120,
        allow_unicode=True,
    )

    notes = card.get("notes") or {}

    body: list[str] = [f"# {card['pretty_name']}", ""]

    general = (notes.get("general") or "").strip()
    if general:
        body.extend([general, ""])

    body.extend([f"**Source:** <{card['source_url']}>", ""])

    body.extend([
        "## Coverage",
        "",
        f"- **Time:** {_format_time_coverage(computed['time_coverage'])}",
        f"- **Cadence:** `{card['cadence']}` "
        f"(observed median spacing: {computed['observed_cadence_days']} days)",
        f"- **Geography levels:** {', '.join(f'`{g}`' for g in card['geography_levels'])} "
        f"— {computed['geography_unit_count']} unique location IDs",
        f"- **Countries:** {', '.join(card['geography_countries'])}",
        f"- **Pathogens:** {', '.join(f'`{p}`' for p in card.get('pathogens', [])) or '—'}",
        f"- **Surveillance category:** `{card.get('surveillance_category')}`",
        f"- **Rows:** {computed['row_count']:,}",
        "",
    ])

    if computed.get("missing_gaps"):
        body.extend([
            "### Reporting gaps within coverage",
            "",
            *(f"- {g['start']} → {g['end']} ({g['weeks']} weeks)" for g in computed["missing_gaps"]),
            "",
        ])

    body.extend([
        "## Columns",
        "",
        _value_columns_table(card.get("value_columns", [])),
        "",
    ])

    extra_cols = notes.get("extra_columns") or []
    if extra_cols:
        body.extend([
            "### Additional data columns",
            "",
            _bullet_list(f"**`{ec['column']}`** — {ec['description']}" for ec in extra_cols),
            "",
        ])

    caveats = notes.get("interpretation_caveats") or []
    if caveats:
        body.extend([
            "## Interpretation caveats",
            "",
            "Things that may differ from how other sources define a similar measure. "
            "If you're combining this dataset with another, read these first.",
            "",
            _bullet_list(f"**`{c['column']}`** — {c['caveat']}" for c in caveats),
            "",
        ])

    relations = _format_relations(card)
    if relations:
        body.extend(["## Related datasets in EPI-Eval", "", _bullet_list(relations), ""])

    body.extend([
        "## Access",
        "",
        f"- **Availability:** `{card['availability']}`",
        f"- **Access type:** `{card['access_type']}`",
        f"- **License:** {card.get('license', 'unspecified')}",
        f"- **Tier:** {card['tier']}",
        "",
    ])

    body.extend([
        "---",
        "",
        f"*Schema version `{card['schema_version']}` · "
        f"Last ingested {computed['last_ingested']} · "
        f"`source_id: {card['source_id']}` · "
        f"Manifest section {card.get('manifest_section', '—')}*",
        "",
    ])

    return f"---\n{frontmatter}---\n\n" + "\n".join(body)


def main() -> int:
    if len(sys.argv) != 2:
        print("Usage: python -m upload_pipeline.core.render_card <source_id>", file=sys.stderr)
        return 2
    source_id = sys.argv[1]
    rendered = render_card(source_id)
    out_path = SOURCES_DIR / source_id / "README.md"
    out_path.write_text(rendered)
    print(f"\nWrote {out_path.relative_to(REPO_ROOT)} ({len(rendered):,} chars)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
