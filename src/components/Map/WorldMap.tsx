import { useEffect, useRef, useState } from "react";
import maplibregl, { type GeoJSONSource, type MapLayerMouseEvent, type Map as MapLibreMap, type FilterSpecification } from "maplibre-gl";
import "maplibre-gl/dist/maplibre-gl.css";
import { buildCountryBoundariesGeoJson, type CountryFeatureProperties } from "./countrySelectionLayer";
import { mapConfig } from "./mapConfig";
import type { SelectedCountry } from "../../types/dashboard";

interface WorldMapProps {
  selectedCountry: SelectedCountry | null;
  onCountrySelect: (country: SelectedCountry | null) => void;
}

const FILL_LAYER = "epieval-country-hit";
const BORDER_LAYER = "epieval-country-border";
const SELECTED_BORDER_LAYER = "epieval-country-selected-border";
const SOURCE_ID = "epieval-countries";

function selectedFilter(iso3: string | null): FilterSpecification {
  return ["==", ["get", "iso3"], iso3 ?? "__none__"] as FilterSpecification;
}

function countryFromProperties(props: CountryFeatureProperties): SelectedCountry {
  return { iso3: props.iso3, isoNumeric: props.isoNumeric, name: props.name };
}

export function WorldMap({ selectedCountry, onCountrySelect }: WorldMapProps) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const mapRef = useRef<MapLibreMap | null>(null);
  const onSelectRef = useRef(onCountrySelect);
  const [ready, setReady] = useState(false);

  useEffect(() => {
    onSelectRef.current = onCountrySelect;
  }, [onCountrySelect]);

  useEffect(() => {
    if (!containerRef.current || mapRef.current) return;

    const map = new maplibregl.Map({
      container: containerRef.current,
      style: mapConfig.styleUrl,
      center: mapConfig.initialCenter,
      zoom: mapConfig.initialZoom,
      minZoom: mapConfig.minZoom,
      maxZoom: mapConfig.maxZoom,
      attributionControl: { compact: true }
    });
    mapRef.current = map;
    map.addControl(new maplibregl.NavigationControl({ showCompass: false }), "top-right");

    const installLayers = () => {
      const data = buildCountryBoundariesGeoJson();

      if (!map.getSource(SOURCE_ID)) {
        map.addSource(SOURCE_ID, { type: "geojson", data, promoteId: "iso3" });
      } else {
        (map.getSource(SOURCE_ID) as GeoJSONSource).setData(data);
      }

      // Invisible fill so clicks register on land but do not flicker.
      if (!map.getLayer(FILL_LAYER)) {
        map.addLayer({
          id: FILL_LAYER,
          type: "fill",
          source: SOURCE_ID,
          paint: { "fill-color": "rgba(0,0,0,0)", "fill-outline-color": "rgba(0,0,0,0)" }
        });
      }
      if (!map.getLayer(BORDER_LAYER)) {
        map.addLayer({
          id: BORDER_LAYER,
          type: "line",
          source: SOURCE_ID,
          paint: { "line-color": "rgba(255,255,255,0.28)", "line-width": 0.6 }
        });
      }
      if (!map.getLayer(SELECTED_BORDER_LAYER)) {
        map.addLayer({
          id: SELECTED_BORDER_LAYER,
          type: "line",
          source: SOURCE_ID,
          filter: selectedFilter(selectedCountry?.iso3 ?? null),
          paint: { "line-color": "#ef4444", "line-width": 1.6 }
        });
      }

      setReady(true);
    };

    map.once("load", () => {
      installLayers();
      map.on("mouseenter", FILL_LAYER, () => {
        map.getCanvas().style.cursor = "pointer";
      });
      map.on("mouseleave", FILL_LAYER, () => {
        map.getCanvas().style.cursor = "";
      });
      map.on("click", FILL_LAYER, (e: MapLayerMouseEvent) => {
        const feature = e.features?.[0];
        if (!feature?.properties) return;
        onSelectRef.current(countryFromProperties(feature.properties as CountryFeatureProperties));
      });
    });

    const fallbackTimer = window.setTimeout(() => {
      if (!map.isStyleLoaded()) {
        map.setStyle(mapConfig.fallbackStyle);
        map.once("style.load", installLayers);
      }
    }, mapConfig.styleLoadTimeoutMs);

    return () => {
      window.clearTimeout(fallbackTimer);
      map.remove();
      mapRef.current = null;
    };
  }, []);

  useEffect(() => {
    if (!mapRef.current || !ready) return;
    mapRef.current.setFilter(SELECTED_BORDER_LAYER, selectedFilter(selectedCountry?.iso3 ?? null));
  }, [selectedCountry?.iso3, ready]);

  const reset = () => {
    mapRef.current?.flyTo({
      center: mapConfig.initialCenter,
      zoom: mapConfig.initialZoom,
      speed: 1.4,
      essential: true
    });
  };

  return (
    <div className="relative h-full min-h-[620px] overflow-hidden rounded-xl border border-white/10 bg-black">
      <div ref={containerRef} className="h-full min-h-[620px] w-full" aria-label="World map" />
      <button
        type="button"
        onClick={reset}
        className="absolute right-3 top-[118px] rounded-md border border-white/15 bg-black/[0.88] px-3 py-2 text-xs font-semibold text-white shadow-lg backdrop-blur hover:border-red-500 hover:text-red-200"
      >
        Reset view
      </button>
    </div>
  );
}
