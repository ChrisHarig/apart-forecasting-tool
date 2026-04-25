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
