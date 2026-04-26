// Pure detection helpers. Given the rows of a dataset, classify which
// boundary set we can render on a map.
//
// EPI-Eval schema (see upload_pipeline/schema/schema_v0.1.md) uses these
// location_id formats:
//   national:           ISO 3166-1 alpha-2 (US, BR, JP)
//   subnational-state:  US 2-digit FIPS (06)  OR  ISO 3166-2 (BR-SP)
//   subnational-county: US 5-digit FIPS (06037)
//   subnational-region: ad-hoc (US-HHS-1) — not standard, we don't render
//   point:              point:<lat>,<lon>
//   facility:           facility:<id>
//   below-ISO 3166-2:   <ISO2>-<NATIVE>-<code>  (BR-IBGE-3550308)
//
// We render polygons for: country, us-state, us-county.
// Everything else falls back to "unsupported" with an explanatory note.

import type { DatasetRow } from "../hf/rows";

export type BoundaryType =
  | "country" // ISO 3166-1 alpha-2 country polygons
  | "us-state" // US 2-digit FIPS state polygons
  | "us-county" // US 5-digit FIPS county polygons
  | "iso3166-2" // first-level subnational outside US — not yet rendered
  | "point" // lat/lon markers — not yet rendered
  | "facility" // named facility — not yet rendered
  | "subnational-region" // ad-hoc regions like US-HHS-1 — not rendered
  | "unsupported";

export interface DetectedLevel {
  level: string; // raw location_level value from the data ("national" / "subnational-state" / etc.)
  boundaryType: BoundaryType;
  ids: Set<string>; // ids appearing in data for this level (matched format)
  rowCount: number;
  unmatchedSamples: string[]; // up to 5 location_id values that didn't match the expected format
}

const FIPS_STATE = /^\d{2}$/;
const FIPS_COUNTY = /^\d{5}$/;
const ISO2 = /^[A-Z]{2}$/;
const ISO_3166_2 = /^[A-Z]{2}-[A-Z0-9]+$/;
const POINT = /^point:.*/;
const FACILITY = /^facility:.*/;

function classifyId(value: string): BoundaryType {
  const v = value.trim();
  if (FIPS_COUNTY.test(v)) return "us-county";
  if (FIPS_STATE.test(v)) return "us-state";
  if (ISO2.test(v)) return "country";
  // ad-hoc regional codes (US-HHS-1, US-CEN-N, etc.) — multi-segment ISO-2 prefixed
  if (/^[A-Z]{2}-[A-Z]+-[A-Z0-9]+$/.test(v)) return "subnational-region";
  if (ISO_3166_2.test(v)) return "iso3166-2";
  if (POINT.test(v)) return "point";
  if (FACILITY.test(v)) return "facility";
  return "unsupported";
}

// Boundary types we have polygon data for.
export function isRenderable(t: BoundaryType): boolean {
  return t === "country" || t === "us-state" || t === "us-county";
}

// Granularity ranking for "default to most granular present" selection. Higher
// = more granular.
const RANK: Record<BoundaryType, number> = {
  "us-county": 4,
  "iso3166-2": 3,
  "us-state": 3,
  "subnational-region": 2,
  country: 1,
  point: 0,
  facility: 0,
  unsupported: -1
};

export function rankBoundary(t: BoundaryType): number {
  return RANK[t] ?? -1;
}

export function detectBoundaryLevels(rows: DatasetRow[]): DetectedLevel[] {
  if (rows.length === 0) return [];

  // Group rows by location_level (or by inferred type when location_level
  // isn't reliable). We cap the per-row cost by sampling up to 5000 rows for
  // detection.
  const sample = rows.length <= 5000 ? rows : rows.slice(0, 5000);

  // Build per (level, boundaryType) bucket. A single dataset can in theory
  // have rows whose location_level says "subnational-state" but whose IDs are
  // ISO 3166-2 (so us-state would be wrong) — we trust the *format* of the
  // location_id over the level label.
  const buckets = new Map<string, DetectedLevel>();

  for (const r of sample) {
    const idRaw = r.location_id;
    if (typeof idRaw !== "string" || idRaw.length === 0) continue;
    const level = typeof r.location_level === "string" && r.location_level.length > 0 ? r.location_level : "(unknown)";
    const boundaryType = classifyId(idRaw);
    const key = `${level}::${boundaryType}`;
    let bucket = buckets.get(key);
    if (!bucket) {
      bucket = {
        level,
        boundaryType,
        ids: new Set(),
        rowCount: 0,
        unmatchedSamples: []
      };
      buckets.set(key, bucket);
    }
    bucket.rowCount++;
    if (boundaryType === "unsupported" && bucket.unmatchedSamples.length < 5 && !bucket.unmatchedSamples.includes(idRaw)) {
      bucket.unmatchedSamples.push(idRaw);
    } else {
      bucket.ids.add(idRaw);
    }
  }

  return Array.from(buckets.values()).sort((a, b) => {
    // Sort renderable types first, then by granularity, then by row count.
    const aRender = isRenderable(a.boundaryType) ? 1 : 0;
    const bRender = isRenderable(b.boundaryType) ? 1 : 0;
    if (aRender !== bRender) return bRender - aRender;
    const aRank = rankBoundary(a.boundaryType);
    const bRank = rankBoundary(b.boundaryType);
    if (aRank !== bRank) return bRank - aRank;
    return b.rowCount - a.rowCount;
  });
}

const BOUNDARY_LABEL: Record<BoundaryType, string> = {
  country: "Countries",
  "us-state": "US states",
  "us-county": "US counties",
  "iso3166-2": "ISO 3166-2 subnational (not yet rendered)",
  "subnational-region": "ad-hoc regions (not rendered)",
  point: "points (not yet rendered)",
  facility: "facilities (not yet rendered)",
  unsupported: "unsupported format"
};

export function boundaryLabel(t: BoundaryType): string {
  return BOUNDARY_LABEL[t];
}
