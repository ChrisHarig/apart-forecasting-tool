// Lazy loaders for us-atlas topojson. Counties is large (~9MB), so we only
// pull it when the user actually selects the US-county view. Vite splits each
// dynamic import into its own chunk.

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

let statesPromise: Promise<FeatureCollection<Geometry, BoundaryFeatureProperties>> | null = null;
export function loadUsStatesGeoJson(): Promise<FeatureCollection<Geometry, BoundaryFeatureProperties>> {
  if (!statesPromise) {
    statesPromise = import("us-atlas/states-10m.json").then((mod) =>
      topologyToCollection(mod.default as unknown as UsTopology, "states")
    );
  }
  return statesPromise;
}

let countiesPromise: Promise<FeatureCollection<Geometry, BoundaryFeatureProperties>> | null = null;
export function loadUsCountiesGeoJson(): Promise<FeatureCollection<Geometry, BoundaryFeatureProperties>> {
  if (!countiesPromise) {
    countiesPromise = import("us-atlas/counties-10m.json").then((mod) =>
      topologyToCollection(mod.default as unknown as UsTopology, "counties")
    );
  }
  return countiesPromise;
}
