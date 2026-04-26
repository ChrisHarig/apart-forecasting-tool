"""Schema validation + computed-metadata derivation for EPI-Eval datasets.

Reads a source's `card.yaml` and its `data/<source_id>.parquet`, cross-checks
both against schema v0.1 and `vocabularies.yaml`, and on success produces the
`computed:` block ready to merge into the rendered dataset card.

Run:
    python -m upload_pipeline.core.validate <source_id>
"""
from __future__ import annotations

import difflib
import hashlib
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import yaml

PRIMARY_KEY_CANDIDATES = ("date", "location_id", "condition", "case_status", "as_of")

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
SCHEMA_DIR = REPO_ROOT / "upload_pipeline" / "schema"
SOURCES_DIR = REPO_ROOT / "upload_pipeline" / "sources"
VOCAB_PATH = SCHEMA_DIR / "vocabularies.yaml"

REQUIRED_CARD_FIELDS = (
    "schema_version", "source_id", "source_url",
    "surveillance_category", "pathogens",
    "availability", "access_type", "tier",
    "cadence", "geography_levels", "geography_countries",
    "value_columns",
)

ENUM_FIELDS = {
    "surveillance_category": "surveillance_category",
    "cadence": "cadence",
    "availability": "availability",
    "access_type": "access_type",
}

ENUM_LIST_FIELDS = {
    "pathogens": "pathogens",
    "geography_levels": "geography_levels",
}

VALUE_COLUMN_REQUIRED = ("name", "unit", "value_type")
VALUE_COLUMN_ENUMS = {
    "value_type": "value_type",
    "aggregation": "aggregation",
}

ROW_LEVEL_CONVENTION_COLS = {
    "date", "location_id", "location_level",
    "location_id_native", "location_name", "as_of",
    "condition", "condition_type", "case_status",
    # `topic` / `topic_type` are the non-illness analog of `condition` /
    # `condition_type` — used for sources whose row variation is a Wikipedia
    # article, search query, news category, mobility category, etc., rather
    # than a pathogen or syndrome. Optional and orthogonal to `condition`.
    "topic", "topic_type",
}

GAP_THRESHOLD_DAYS = {
    "daily": 14, "weekly": 28, "biweekly": 56,
    "monthly": 90, "quarterly": 270, "annual": 730,
    "irregular": 365,
}

EXPECTED_CADENCE_DAYS = {
    "daily": 1, "weekly": 7, "biweekly": 14,
    "monthly": 30, "quarterly": 91, "annual": 365,
}


def load_vocabularies() -> dict:
    return yaml.safe_load(VOCAB_PATH.read_text())


def load_location_registries() -> dict[str, set[str]]:
    """Load all schema/locations/*.yaml registries.

    Returns a dict mapping registry-name → set of recognised codes. The
    validator treats unknown codes as a warning, not an error — registries
    are advisory for display-name lookup, not a gate.
    """
    out: dict[str, set[str]] = {}
    locations_dir = SCHEMA_DIR / "locations"
    if not locations_dir.exists():
        return out
    for path in sorted(locations_dir.glob("*.yaml")):
        data = yaml.safe_load(path.read_text()) or {}
        codes: set[str] = set()
        for key in ("codes", "catchment_codes"):
            if isinstance(data.get(key), dict):
                codes.update(data[key].keys())
        if codes:
            out[path.stem] = codes
    return out


def fuzzy_suggest(value, allowed: list) -> str:
    matches = difflib.get_close_matches(
        str(value).lower(),
        [str(a).lower() for a in allowed],
        n=1, cutoff=0.6,
    )
    return f" Did you mean {matches[0]!r}?" if matches else ""


def _check_enum(value, field_name: str, allowed: list, errors: list) -> None:
    if value not in allowed:
        errors.append(
            f"{field_name}={value!r} is not in vocabularies.yaml.{fuzzy_suggest(value, allowed)}"
        )


VINTAGING_MODES = {"full", "latest", "none"}


def validate_card(card: dict, vocab: dict) -> list[str]:
    errors: list[str] = []

    for field in REQUIRED_CARD_FIELDS:
        if field not in card:
            errors.append(f"Required field missing: {field}")

    if card.get("schema_version") != "0.1":
        errors.append(
            f"Unsupported schema_version: {card.get('schema_version')!r} (expected '0.1')"
        )

    for field, vocab_key in ENUM_FIELDS.items():
        if field in card:
            _check_enum(card[field], field, vocab[vocab_key], errors)

    for field, vocab_key in ENUM_LIST_FIELDS.items():
        for value in card.get(field, []) or []:
            _check_enum(value, f"{field}[]", vocab[vocab_key], errors)

    for cc in card.get("geography_countries", []) or []:
        if cc != "multiple" and not (isinstance(cc, str) and len(cc) == 2 and cc.isupper()):
            errors.append(
                f"geography_countries[{cc!r}] is not a 2-letter ISO code or 'multiple'"
            )

    if card.get("tier") not in (1, 2, 3):
        errors.append(f"tier={card.get('tier')!r} must be 1, 2, or 3")

    for vc in card.get("value_columns", []) or []:
        name = vc.get("name", "?")
        for k in VALUE_COLUMN_REQUIRED:
            if k not in vc:
                errors.append(f"value_columns[{name!r}] missing required key: {k}")
        for field, vocab_key in VALUE_COLUMN_ENUMS.items():
            if field in vc:
                _check_enum(vc[field], f"value_columns[{name!r}].{field}",
                            vocab[vocab_key], errors)

    vintaging = card.get("vintaging")
    if vintaging is not None:
        mode = vintaging.get("mode")
        if mode not in VINTAGING_MODES:
            errors.append(
                f"vintaging.mode={mode!r} must be one of {sorted(VINTAGING_MODES)}"
            )

    return errors


def _location_id_matches_level(loc_id, level: str) -> bool:
    if not isinstance(loc_id, str):
        return False
    if level == "national":
        return bool(re.fullmatch(r"[A-Z]{2}", loc_id))
    if level == "subnational-state":
        return bool(
            re.fullmatch(r"\d{2}", loc_id)
            or re.fullmatch(r"[A-Z]{2}-[A-Z0-9]{1,3}", loc_id)
        )
    if level == "subnational-county":
        return bool(re.fullmatch(r"\d{5}", loc_id))
    if level == "subnational-region":
        return bool(re.fullmatch(r"[A-Z]{2}-[A-Z]+(?:-[A-Z0-9]+)+", loc_id))
    if level == "subnational-city":
        return bool(re.fullmatch(r"[A-Z]{2}-[A-Z0-9]+(-[A-Z0-9]+)*", loc_id))
    if level == "point":
        return loc_id.startswith("point:")
    if level == "facility":
        return loc_id.startswith("facility:")
    if level == "global":
        return loc_id in ("WORLD", "GLOBAL")
    return True


def validate_data(df: pd.DataFrame, card: dict, vocab: dict) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []

    for col in ("date", "location_id", "location_level"):
        if col not in df.columns:
            errors.append(f"Required data column missing: {col}")
    if errors:
        return errors, warnings

    for col in ("date", "location_id", "location_level"):
        n_null = int(df[col].isna().sum())
        if n_null > 0:
            errors.append(f"Column {col!r} has {n_null} null values; required columns must never be null")

    if not pd.api.types.is_datetime64_any_dtype(df["date"]):
        errors.append(f"date column has dtype {df['date'].dtype}; must be datetime")
    elif getattr(df["date"].dt, "tz", None) is None:
        errors.append("date column is timezone-naive; must be UTC")

    for level in df["location_level"].dropna().unique():
        if level not in vocab["geography_levels"]:
            errors.append(
                f"location_level={level!r} not in vocabularies.yaml."
                f"{fuzzy_suggest(level, vocab['geography_levels'])}"
            )

    bad_pairs = []
    pairs = df[["location_id", "location_level"]].drop_duplicates()
    for _, row in pairs.iterrows():
        if not _location_id_matches_level(row["location_id"], row["location_level"]):
            bad_pairs.append((row["location_id"], row["location_level"]))
    if bad_pairs:
        sample = bad_pairs[:5]
        errors.append(
            f"{len(bad_pairs)} (location_id, location_level) pairs don't match conventions; "
            f"first few: {sample}"
        )

    # Advisory: cross-check synthetic / sub-state location_ids against the
    # locations registry. Unknowns surface as warnings — the registry is for
    # display-name lookup, not a gate. Hard-coded codes (FIPS, ISO) handled
    # by the regex pattern check above.
    registries = load_location_registries()
    if registries:
        all_known: set[str] = set().union(*registries.values())
        unknown_synthetic = []
        for loc_id in df["location_id"].dropna().unique():
            # Only check synthetic prefixes — bare FIPS / ISO already validated by regex.
            if "-" in loc_id and any(loc_id.startswith(p) for p in ("US-METRO-", "US-FLUSURV-", "US-HHS-")):
                if loc_id not in all_known:
                    unknown_synthetic.append(loc_id)
        if unknown_synthetic:
            sample = sorted(set(unknown_synthetic))[:8]
            warnings.append(
                f"{len(set(unknown_synthetic))} location_id(s) not in locations registry; "
                f"add them to upload_pipeline/schema/locations/ if they're real. Sample: {sample}"
            )

    declared = {vc["name"] for vc in card.get("value_columns", []) if "name" in vc}
    documented_extras = {
        ec.get("column")
        for ec in (card.get("notes", {}) or {}).get("extra_columns", []) or []
        if ec.get("column")
    }
    data_value_cols = set(df.columns) - ROW_LEVEL_CONVENTION_COLS - documented_extras

    missing_in_data = declared - set(df.columns)
    if missing_in_data:
        errors.append(
            f"Declared in card.value_columns but missing from data: {sorted(missing_in_data)}"
        )

    undeclared_in_data = data_value_cols - declared
    if undeclared_in_data:
        errors.append(
            f"Data columns not declared in value_columns or notes.extra_columns: "
            f"{sorted(undeclared_in_data)}"
        )

    declared_present = [vc["name"] for vc in card.get("value_columns", [])
                        if vc.get("name") in df.columns]

    for col in declared_present:
        n_null = int(df[col].isna().sum())
        if n_null == len(df):
            warnings.append(
                f"Column {col!r} is entirely NaN; consider removing from value_columns"
            )

    if declared_present:
        all_nan_rows = int(df[declared_present].isna().all(axis=1).sum())
        if all_nan_rows > 0:
            warnings.append(
                f"{all_nan_rows} rows have NaN in every declared value column"
            )

    # Sentinel detection — only flag values that are implausible as real measurements
    # (negative numbers in count columns; unusually high frequency of a single value).
    # Don't flag positive numbers like 999 — those are plausible real counts.
    for col in declared_present:
        if not pd.api.types.is_numeric_dtype(df[col]):
            continue
        for sentinel in (-1, -999):
            n_hit = int((df[col] == sentinel).sum())
            if n_hit > 0:
                warnings.append(
                    f"Column {col!r} contains {n_hit} occurrences of {sentinel}; "
                    f"coerce to NaN if these represent missing data"
                )
                break

    vintaging = card.get("vintaging") or {}
    if vintaging.get("mode") == "full" and "as_of" not in df.columns:
        errors.append(
            "vintaging.mode=full but no `as_of` row column present in the data; "
            "full vintaging requires snapshot dates per row"
        )

    declared_cadence = card.get("cadence")
    if declared_cadence in EXPECTED_CADENCE_DAYS:
        # Dedupe (date, location_id) so long-format sources (multiple rows per
        # date/location with different `condition` values) don't get a 0-day diff.
        per_loc_dates = df[["date", "location_id"]].drop_duplicates()
        per_loc_medians = []
        for _, group in per_loc_dates.groupby("location_id"):
            if len(group) > 1:
                d = group["date"].sort_values().diff().dropna().dt.days
                if len(d) > 0:
                    per_loc_medians.append(float(d.median()))
        if per_loc_medians:
            observed = float(pd.Series(per_loc_medians).median())
            expected = EXPECTED_CADENCE_DAYS[declared_cadence]
            if abs(observed - expected) > expected * 0.5:
                warnings.append(
                    f"Declared cadence={declared_cadence!r} (~{expected}d) but observed median "
                    f"spacing per location is {observed:.1f}d"
                )

    return errors, warnings


def compute_data_hash(df: pd.DataFrame) -> str:
    """Deterministic 16-char hash of DataFrame contents.

    Sorts by primary key + canonical column order before hashing so re-runs
    of the same source data produce identical hashes. NaN-safe.
    """
    sort_keys = [c for c in PRIMARY_KEY_CANDIDATES if c in df.columns]
    df_sorted = df.sort_values(sort_keys, kind="stable").reset_index(drop=True)
    df_sorted = df_sorted[sorted(df_sorted.columns)]
    row_hashes = pd.util.hash_pandas_object(df_sorted, index=False).values
    return hashlib.sha256(row_hashes.tobytes()).hexdigest()[:16]


def compute_diff(prev_df: pd.DataFrame, new_df: pd.DataFrame) -> dict:
    """Count rows added/removed/revised between two DataFrames.

    Uses (date, location_id, condition, case_status) as the row identity key
    where present. Returns a dict suitable for embedding in a commit message.
    """
    key_cols = [c for c in ("date", "location_id", "condition", "case_status")
                if c in prev_df.columns and c in new_df.columns]

    if not key_cols:
        return {
            "added": None, "removed": None, "revised": None,
            "rows_prev": len(prev_df), "rows_new": len(new_df),
        }

    prev_keyed = prev_df.set_index(key_cols).sort_index()
    new_keyed = new_df.set_index(key_cols).sort_index()

    prev_keys = set(prev_keyed.index)
    new_keys = set(new_keyed.index)

    added = len(new_keys - prev_keys)
    removed = len(prev_keys - new_keys)

    common = list(new_keys & prev_keys)
    revised = 0
    if common:
        common_cols = [c for c in prev_keyed.columns if c in new_keyed.columns]
        prev_common = prev_keyed.loc[common, common_cols]
        new_common = new_keyed.loc[common, common_cols]
        # Cell-by-cell, treating NaN==NaN as equal.
        cell_diff = (prev_common != new_common) & ~(prev_common.isna() & new_common.isna())
        revised = int(cell_diff.any(axis=1).sum())

    return {
        "added": added, "removed": removed, "revised": revised,
        "rows_prev": len(prev_df), "rows_new": len(new_df),
    }


def compute_metadata(df: pd.DataFrame, card: dict) -> dict:
    cadence = card.get("cadence", "weekly")
    gap_days = GAP_THRESHOLD_DAYS.get(cadence, 28)

    dates_unique = sorted(pd.to_datetime(df["date"], utc=True).dt.normalize().unique())
    dates_unique = [pd.Timestamp(d) for d in dates_unique]

    intervals: list[dict] = []
    if dates_unique:
        start = dates_unique[0]
        prev = dates_unique[0]
        for d in dates_unique[1:]:
            if (d - prev).days > gap_days:
                intervals.append({
                    "start": start.strftime("%Y-%m-%d"),
                    "end": prev.strftime("%Y-%m-%d"),
                })
                start = d
            prev = d
        intervals.append({
            "start": start.strftime("%Y-%m-%d"),
            "end": prev.strftime("%Y-%m-%d"),
        })

    cadence_days = EXPECTED_CADENCE_DAYS.get(cadence, 7)
    missing_gaps: list[dict] = []
    for i in range(1, len(dates_unique)):
        gap = (dates_unique[i] - dates_unique[i - 1]).days
        if gap > gap_days:
            continue
        if gap > cadence_days * 2:
            missing_gaps.append({
                "start": dates_unique[i - 1].strftime("%Y-%m-%d"),
                "end": dates_unique[i].strftime("%Y-%m-%d"),
                "weeks": int(round(gap / 7)),
            })

    observed_cadence_days = None
    if len(dates_unique) > 1:
        diffs = pd.Series([(dates_unique[i] - dates_unique[i - 1]).days
                           for i in range(1, len(dates_unique))])
        observed_cadence_days = int(diffs.median())

    return {
        "last_ingested": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "row_count": int(len(df)),
        "time_coverage": intervals,
        "geography_unit_count": int(df["location_id"].nunique()),
        "observed_cadence_days": observed_cadence_days,
        "missing_gaps": missing_gaps,
        "data_hash": compute_data_hash(df),
    }


def validate_source(source_id: str) -> dict:
    source_dir = SOURCES_DIR / source_id
    card_path = source_dir / "card.yaml"
    data_path = source_dir / "data" / f"{source_id}.parquet"

    if not card_path.exists():
        raise FileNotFoundError(f"card.yaml not found: {card_path}")
    if not data_path.exists():
        raise FileNotFoundError(f"data parquet not found: {data_path}")

    card = yaml.safe_load(card_path.read_text())
    df = pd.read_parquet(data_path)
    vocab = load_vocabularies()

    print(f"Validating {source_id}")
    print(f"  card: {card_path.relative_to(REPO_ROOT)}")
    print(f"  data: {data_path.relative_to(REPO_ROOT)} "
          f"({len(df):,} rows × {len(df.columns)} columns)")
    print()

    errors = validate_card(card, vocab)
    data_errors, warnings = validate_data(df, card, vocab)
    errors.extend(data_errors)

    if errors:
        print(f"FAIL — {len(errors)} error(s):")
        for e in errors:
            print(f"  - {e}")
    else:
        print("PASS — schema + data validation OK")

    if warnings:
        print(f"\n{len(warnings)} warning(s):")
        for w in warnings:
            print(f"  - {w}")

    if not errors:
        computed = compute_metadata(df, card)
        print("\nComputed metadata:")
        print(yaml.safe_dump({"computed": computed}, sort_keys=False, default_flow_style=False))
        return {"errors": [], "warnings": warnings, "computed": computed}

    return {"errors": errors, "warnings": warnings, "computed": None}


def main() -> int:
    if len(sys.argv) != 2:
        print("Usage: python -m upload_pipeline.core.validate <source_id>", file=sys.stderr)
        return 2
    result = validate_source(sys.argv[1])
    return 0 if not result["errors"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
