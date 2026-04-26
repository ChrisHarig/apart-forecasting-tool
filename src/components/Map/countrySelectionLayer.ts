import countries50m from "world-atlas/countries-50m.json";
import { feature } from "topojson-client";
import type { Feature, FeatureCollection, Geometry } from "geojson";
import type { GeometryCollection, Objects, Topology } from "topojson-specification";
import { getCountryReferenceFromNumeric } from "../../utils/countryCodes";

export interface CountryFeatureProperties {
  iso3: string;
  isoNumeric: string;
  name: string;
  sourceCoverageCount: number;
}

export type CountryFeatureCollection = FeatureCollection<Geometry, CountryFeatureProperties>;

type TopologyWithCountries = Topology<Objects<{ name?: string }>> & {
  objects: {
    countries: GeometryCollection<{ name?: string }>;
  };
};

function closeRing(ring: number[][]): number[][] {
  if (ring.length === 0) return ring;
  const first = ring[0];
  const last = ring[ring.length - 1];
  if (first[0] === last[0] && first[1] === last[1]) return ring;
  return [...ring, [...first]];
}

function unwrapRingAtAntimeridian(ring: number[][]): number[][] {
  if (ring.length < 2) return ring;

  const unwrapped: number[][] = [[...ring[0]]];
  let longitudeOffset = 0;
  let previousLongitude = ring[0][0];

  for (let index = 1; index < ring.length; index += 1) {
    const point = ring[index];
    let longitude = point[0] + longitudeOffset;
    const delta = longitude - previousLongitude;

    if (delta > 180) {
      longitudeOffset -= 360;
      longitude -= 360;
    } else if (delta < -180) {
      longitudeOffset += 360;
      longitude += 360;
    }

    unwrapped.push([longitude, ...point.slice(1)]);
    previousLongitude = longitude;
  }

  return closeRing(unwrapped);
}

function unwrapGeometryAtAntimeridian(geometry: Geometry): Geometry {
  if (geometry.type !== "Polygon" && geometry.type !== "MultiPolygon") return geometry;

  if (geometry.type === "Polygon") {
    return {
      ...geometry,
      coordinates: geometry.coordinates.map(unwrapRingAtAntimeridian)
    };
  }

  return {
    ...geometry,
    coordinates: geometry.coordinates.map((polygon) => polygon.map(unwrapRingAtAntimeridian))
  };
}

export function buildCountrySelectionGeoJson(coverageCounts: Record<string, number> = {}): CountryFeatureCollection {
  const topology = countries50m as unknown as TopologyWithCountries;
  const collection = feature(topology, topology.objects.countries) as unknown as FeatureCollection<Geometry, { name?: string }>;
  const features = collection.features
    .map((countryFeature) => {
      const isoNumeric = String(countryFeature.id ?? "").padStart(3, "0");
      const reference = getCountryReferenceFromNumeric(isoNumeric);
      if (!reference) return null;
      return {
        ...countryFeature,
        geometry: unwrapGeometryAtAntimeridian(countryFeature.geometry),
        properties: {
          iso3: reference.iso3,
          isoNumeric,
          name: countryFeature.properties?.name ?? reference.name,
          sourceCoverageCount: coverageCounts[reference.iso3] ?? 0
        }
      } satisfies Feature<Geometry, CountryFeatureProperties>;
    })
    .filter((item): item is Feature<Geometry, CountryFeatureProperties> => Boolean(item));

  return {
    type: "FeatureCollection",
    features
  };
}
