// Lazy loader for ISO 3166-2 first-level subnational boundaries.
//
// Source: Natural Earth 1:10m admin-1 (`ne_10m_admin_1_states_provinces`),
// filtered to ~68 countries we currently care about and Douglas-Peucker
// simplified at ~5 km tolerance. Vendored at
// `src/assets/geojson/admin1-50m.geo.json` (2.2 MB).
//
// Caching:
//   - The full file load is module-cached via `allPromise` — only one
//     dynamic import per session.
//   - Per-country-set filter results are cached in `filteredByKey` so the
//     second open of the same dataset (or any dataset with the same set
//     of countries) reuses the same FeatureCollection by reference.
//
// Coverage caveats:
//   - Some countries' admin-1 in Natural Earth represents the *second*-level
//     admin division, not the ISO 3166-2 first-level region. Examples:
//       UK: 232 districts/boroughs, not the 4 constituent countries
//       France: départements, not régions
//       Italy: 110 provinces, not 20 regions
//     For sources that publish at the true first-level (UKHSA `GB-ENG`,
//     Sentinelles France `FR-IDF`), the iso_3166_2 join misses. The caller
//     should fall back to country-level rendering when this happens — see
//     DatasetMap's country-aggregation level option.
//   - Countries not in the curated list above don't render at admin-1 even
//     if they have rows in the data; same fall-back to country-level.

import type { Feature, FeatureCollection, Geometry } from "geojson";

import type { BoundaryFeatureProperties } from "./usAtlas";

interface RawProperties {
  iso_3166_2?: string;
  iso_a2?: string;
  name?: string;
  admin?: string;
}

let allPromise: Promise<FeatureCollection<Geometry, BoundaryFeatureProperties>> | null = null;

function logTiming(label: string, t0: number, n?: number): void {
  const ms = (performance.now() - t0).toFixed(0);
  const count = n !== undefined ? ` (${n} features)` : "";
  console.info(`[locations] ${label} in ${ms}ms${count}`);
}

function loadAll(): Promise<FeatureCollection<Geometry, BoundaryFeatureProperties>> {
  if (!allPromise) {
    const t0 = performance.now();
    allPromise = import("../../assets/geojson/admin1-50m.geo.json")
      .then((mod) => {
        const tParsed = performance.now();
        logTiming("loadIso3166_2 chunk fetch+parse", t0);
        const raw = mod.default as FeatureCollection<Geometry, RawProperties>;
        const features = raw.features
          .filter((f) => typeof f.properties?.iso_3166_2 === "string" && f.properties.iso_3166_2.length > 0)
          .map((f) => ({
            ...f,
            properties: {
              id: f.properties!.iso_3166_2 as string,
              name: f.properties!.name ?? ""
            }
          })) satisfies Feature<Geometry, BoundaryFeatureProperties>[];
        logTiming("loadIso3166_2 reshape", tParsed, features.length);
        return { type: "FeatureCollection" as const, features };
      })
      .catch((err) => {
        // Drop the cached promise so a manual retry has a chance.
        allPromise = null;
        console.error("[locations] loadIso3166_2 failed", err);
        throw err;
      });
  }
  return allPromise;
}

// Per-country-set filter cache. Key is a sorted, comma-joined string of the
// countries; value is the filtered FeatureCollection by reference, so the
// second open of UKHSA or PHAC reuses the exact same object.
const filteredByKey = new Map<string, FeatureCollection<Geometry, BoundaryFeatureProperties>>();

function cacheKey(countries: ReadonlySet<string>): string {
  return Array.from(countries).sort().join(",");
}

/**
 * Load admin-1 polygons, filtered to features whose iso_3166_2 starts with
 * any of the supplied ISO-2 country codes. Pass an empty set to load
 * everything (rare).
 */
export async function loadIso3166_2GeoJson(
  countries: ReadonlySet<string>
): Promise<FeatureCollection<Geometry, BoundaryFeatureProperties>> {
  const all = await loadAll();
  if (countries.size === 0) return all;
  const key = cacheKey(countries);
  const cached = filteredByKey.get(key);
  if (cached) return cached;
  const t0 = performance.now();
  const filtered: FeatureCollection<Geometry, BoundaryFeatureProperties> = {
    type: "FeatureCollection",
    features: all.features.filter((f) => {
      const id = f.properties?.id;
      if (typeof id !== "string") return false;
      const cc = id.slice(0, 2);
      return countries.has(cc);
    })
  };
  filteredByKey.set(key, filtered);
  logTiming(`loadIso3166_2GeoJson filter [${key}]`, t0, filtered.features.length);
  return filtered;
}

// Test-only: clear all caches. Exported so unit tests can isolate runs.
export function _resetIso3166_2CachesForTests(): void {
  allPromise = null;
  filteredByKey.clear();
}
