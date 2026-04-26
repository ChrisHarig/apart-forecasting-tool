// Lazy loader for ISO 3166-2 first-level subnational boundaries.
//
// Source: Natural Earth 1:10m admin-1 (`ne_10m_admin_1_states_provinces`),
// filtered to ~68 countries we currently care about and Douglas-Peucker
// simplified at ~5 km tolerance. Vendored at
// `src/assets/geojson/admin1-50m.geo.json` (2.2 MB).
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

function loadAll(): Promise<FeatureCollection<Geometry, BoundaryFeatureProperties>> {
  if (!allPromise) {
    allPromise = import("../../assets/geojson/admin1-50m.geo.json").then((mod) => {
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
      return { type: "FeatureCollection", features };
    });
  }
  return allPromise;
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
  const features = all.features.filter((f) => {
    const id = f.properties?.id;
    if (typeof id !== "string") return false;
    const cc = id.slice(0, 2);
    return countries.has(cc);
  });
  return { type: "FeatureCollection", features };
}
