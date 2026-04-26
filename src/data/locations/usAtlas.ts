// Lazy loaders for us-atlas topojson. Counties is large (~9MB), so we only
// pull it when the user actually selects the US-county view. Vite splits each
// dynamic import into its own chunk.
//
// All loaders are module-cached via singleton promises — every caller waits
// on the same in-flight load. Timing is logged so a stuck dynamic import is
// observable in the browser console (FOLLOW_UPS #4).

import { feature } from "topojson-client";
import type { Feature, FeatureCollection, Geometry } from "geojson";
import type { GeometryCollection, Objects, Topology } from "topojson-specification";

export interface BoundaryFeatureProperties {
  id: string;
  name: string;
}

type UsTopology = Topology<Objects<{ name?: string }>> & {
  objects: Record<string, GeometryCollection<{ name?: string }>>;
};

function topologyToCollection(topology: UsTopology, objectKey: string): FeatureCollection<Geometry, BoundaryFeatureProperties> {
  const collection = feature(topology, topology.objects[objectKey]) as unknown as FeatureCollection<Geometry, { name?: string }>;
  const features = collection.features.map((f) => ({
    ...f,
    properties: {
      id: String(f.id ?? ""),
      name: f.properties?.name ?? ""
    }
  })) satisfies Feature<Geometry, BoundaryFeatureProperties>[];
  return { type: "FeatureCollection", features };
}

function logTiming(label: string, t0: number, n?: number): void {
  const ms = (performance.now() - t0).toFixed(0);
  const count = n !== undefined ? ` (${n} features)` : "";
  console.info(`[locations] ${label} in ${ms}ms${count}`);
}

let statesPromise: Promise<FeatureCollection<Geometry, BoundaryFeatureProperties>> | null = null;
export function loadUsStatesGeoJson(): Promise<FeatureCollection<Geometry, BoundaryFeatureProperties>> {
  if (!statesPromise) {
    const t0 = performance.now();
    statesPromise = import("us-atlas/states-10m.json")
      .then((mod) => {
        const t1 = performance.now();
        const fc = topologyToCollection(mod.default as unknown as UsTopology, "states");
        logTiming(`loadUsStatesGeoJson chunk fetch+parse`, t0);
        logTiming(`loadUsStatesGeoJson topology→features`, t1, fc.features.length);
        return fc;
      })
      .catch((err) => {
        // Drop the cached promise so a manual retry has a chance.
        statesPromise = null;
        console.error("[locations] loadUsStatesGeoJson failed", err);
        throw err;
      });
  }
  return statesPromise;
}

let countiesPromise: Promise<FeatureCollection<Geometry, BoundaryFeatureProperties>> | null = null;
export function loadUsCountiesGeoJson(): Promise<FeatureCollection<Geometry, BoundaryFeatureProperties>> {
  if (!countiesPromise) {
    const t0 = performance.now();
    countiesPromise = import("us-atlas/counties-10m.json")
      .then((mod) => {
        const t1 = performance.now();
        const fc = topologyToCollection(mod.default as unknown as UsTopology, "counties");
        logTiming(`loadUsCountiesGeoJson chunk fetch+parse`, t0);
        logTiming(`loadUsCountiesGeoJson topology→features`, t1, fc.features.length);
        return fc;
      })
      .catch((err) => {
        countiesPromise = null;
        console.error("[locations] loadUsCountiesGeoJson failed", err);
        throw err;
      });
  }
  return countiesPromise;
}
