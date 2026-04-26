import { useEffect, useMemo, useRef, useState } from "react";
import maplibregl, { type FilterSpecification, type GeoJSONSource, type MapLayerMouseEvent, type Map as MapLibreMap } from "maplibre-gl";
import "maplibre-gl/dist/maplibre-gl.css";
import type { SelectedCountry } from "../../types/dashboard";
import { buildCountrySelectionGeoJson, type CountryFeatureProperties } from "./countrySelectionLayer";
import { mapConfig } from "./mapConfig";

interface WorldMapProps {
  selectedCountry: SelectedCountry | null;
  coverageCounts: Record<string, number>;
  onCountrySelect: (country: SelectedCountry) => void;
  onCountryHover: (country: SelectedCountry | null) => void;
}

function selectedFilter(iso3: string | null): FilterSpecification {
  return ["==", ["get", "iso3"], iso3 ?? "__none__"] as FilterSpecification;
}

function countryFromProperties(properties: CountryFeatureProperties): SelectedCountry {
  return {
    iso3: properties.iso3,
    isoNumeric: properties.isoNumeric,
    name: properties.name
  };
}

export function WorldMap({ selectedCountry, coverageCounts, onCountrySelect, onCountryHover }: WorldMapProps) {
  const countryGeoJson = useMemo(() => buildCountrySelectionGeoJson(coverageCounts), [coverageCounts]);
  const mapContainerRef = useRef<HTMLDivElement | null>(null);
  const mapRef = useRef<MapLibreMap | null>(null);
  const countryGeoJsonRef = useRef(countryGeoJson);
  const [mapReady, setMapReady] = useState(false);

  useEffect(() => {
    countryGeoJsonRef.current = countryGeoJson;
  }, [countryGeoJson]);

  useEffect(() => {
    if (!mapContainerRef.current || mapRef.current) return;
    let interactionsAttached = false;
    let fallbackApplied = false;

    const map = new maplibregl.Map({
      container: mapContainerRef.current,
      style: mapConfig.styleUrl,
      center: mapConfig.initialCenter,
      zoom: mapConfig.initialZoom,
      minZoom: mapConfig.minZoom,
      maxZoom: mapConfig.maxZoom,
      renderWorldCopies: false,
      attributionControl: { compact: true }
    });

    mapRef.current = map;
    map.addControl(new maplibregl.NavigationControl({ showCompass: false }), "top-right");

    const attachInteractions = () => {
      if (interactionsAttached) return;
      interactionsAttached = true;

      map.on("mousemove", "sentinel-country-fill", (event: MapLayerMouseEvent) => {
        const feature = event.features?.[0];
        if (!feature?.properties) return;
        const properties = feature.properties as CountryFeatureProperties;
        const country = countryFromProperties(properties);
        onCountryHover(country);
        map.getCanvas().style.cursor = "pointer";
      });

      map.on("mouseleave", "sentinel-country-fill", () => {
        onCountryHover(null);
        map.getCanvas().style.cursor = "";
      });

      map.on("click", "sentinel-country-fill", (event: MapLayerMouseEvent) => {
        const feature = event.features?.[0];
        if (!feature?.properties) return;
        onCountrySelect(countryFromProperties(feature.properties as CountryFeatureProperties));
      });
    };

    const installCountryLayers = () => {
      if (map.getSource("sentinel-countries")) {
        const source = map.getSource("sentinel-countries") as GeoJSONSource;
        source.setData(countryGeoJsonRef.current);
      } else {
        map.addSource("sentinel-countries", {
          type: "geojson",
          data: countryGeoJsonRef.current,
          promoteId: "iso3"
        });
      }

      if (map.getLayer("sentinel-country-fill")) {
        attachInteractions();
        setMapReady(true);
        return;
      }

      map.addLayer({
        id: "sentinel-country-fill",
        type: "fill",
        source: "sentinel-countries",
        paint: {
          "fill-color": [
            "step",
            ["get", "sourceCoverageCount"],
            "rgba(255,255,255,0.035)",
            1,
            "rgba(255,255,255,0.055)",
            3,
            "rgba(255,255,255,0.075)",
            6,
            "rgba(255,255,255,0.095)"
          ],
          "fill-outline-color": "rgba(255,255,255,0)"
        }
      });

      if (fallbackApplied) {
        map.addLayer({
          id: "sentinel-fallback-country-line",
          type: "line",
          source: "sentinel-countries",
          paint: {
            "line-color": "rgba(255,255,255,0.20)",
            "line-width": 0.45
          }
        });
      }

      map.addLayer({
        id: "sentinel-selected-country-fill",
        type: "fill",
        source: "sentinel-countries",
        filter: selectedFilter(selectedCountry?.iso3 ?? null),
        paint: {
          "fill-color": "rgba(220,38,38,0.42)",
          "fill-outline-color": "rgba(220,38,38,0)"
        }
      });

      attachInteractions();
      setMapReady(true);
    };

    map.on("load", installCountryLayers);
    map.on("style.load", installCountryLayers);

    const fallbackTimer = window.setTimeout(() => {
      if (fallbackApplied || map.isStyleLoaded()) return;
      fallbackApplied = true;
      map.setStyle(mapConfig.fallbackStyle);
    }, mapConfig.styleLoadTimeoutMs);

    return () => {
      window.clearTimeout(fallbackTimer);
      map.remove();
      mapRef.current = null;
    };
  }, []);

  useEffect(() => {
    if (!mapRef.current || !mapReady) return;
    const source = mapRef.current.getSource("sentinel-countries") as GeoJSONSource | undefined;
    source?.setData(countryGeoJson);
  }, [countryGeoJson, mapReady]);

  useEffect(() => {
    if (!mapRef.current || !mapReady) return;
    mapRef.current.setFilter("sentinel-selected-country-fill", selectedFilter(selectedCountry?.iso3 ?? null));
  }, [selectedCountry?.iso3, mapReady]);

  const resetMap = () => {
    mapRef.current?.flyTo({
      center: mapConfig.initialCenter,
      zoom: mapConfig.initialZoom,
      speed: 1.4,
      essential: true
    });
  };

  return (
    <div className="relative h-full min-h-[620px] overflow-hidden rounded-xl border border-white/10 bg-black">
      <div ref={mapContainerRef} className="h-full min-h-[620px] w-full" aria-label="Interactive world map" />

      <button
        type="button"
        className="absolute right-3 top-[118px] rounded-md border border-white/15 bg-black/[0.88] px-3 py-2 text-xs font-semibold text-white shadow-lg backdrop-blur transition hover:border-red-500 hover:text-red-100"
        onClick={resetMap}
      >
        Reset view
      </button>
    </div>
  );
}
