// Generic polygon-boundary map. Takes whatever GeoJSON the caller provides
// (countries / US states / US counties / ...) and renders it on a self-
// contained ocean-only base style. Three layered fills surface the dataset
// status of each region:
//
//   - everything: a faint "land" fill so unmapped regions still read as land
//   - in scope but missing: a brighter neutral fill (e.g. a state in the US
//     scope that didn't report)
//   - has data: a saturated red fill
//
// Plus a thin border on every region and a bright red border on the current
// selection. The id field used as the highlight key is `properties.id` on
// each feature; callers reshape their geojson to match.

import { useEffect, useRef, useState } from "react";
import maplibregl, {
  type FilterSpecification,
  type GeoJSONSource,
  type Map as MapLibreMap,
  type MapLayerMouseEvent
} from "maplibre-gl";
import "maplibre-gl/dist/maplibre-gl.css";
import type { FeatureCollection, Geometry } from "geojson";
import { mapColors, mapConfig } from "./mapConfig";
import { buildCountryBoundariesGeoJson } from "./countrySelectionLayer";

export interface BoundaryFeatureProps {
  id: string;
  name: string;
}

export interface BoundarySelection {
  id: string;
  name: string;
}

interface Props {
  geojson: FeatureCollection<Geometry, BoundaryFeatureProps>;
  // Regions that have at least one row in the dataset. Painted as `hasData`
  // when no chloropleth is active (binary mode).
  highlightedIds: ReadonlySet<string>;
  // Regions the dataset is *expected* to cover but for which no rows exist.
  // Painted as `scopeMissing`. When undefined or empty, no missing-data layer
  // is rendered (e.g. country datasets where geography_countries = "multiple").
  scopeIds?: ReadonlySet<string>;
  // Chloropleth mode: when present, replaces the binary has-data fill with a
  // value-driven fill. Values must be normalized to [0, 1]; the map paints
  // `0` as faint red and `1` as saturated red, with anything outside that
  // range (or unset) treated as "no data" and left transparent.
  valueByLocation?: ReadonlyMap<string, number>;
  selected: BoundarySelection | null;
  onSelect: (selection: BoundarySelection | null) => void;
  // Optional initial fit-bounds rectangle, e.g. for US-only boundaries.
  initialBounds?: [[number, number], [number, number]];
}

const FILL_LAYER = "epieval-boundary-hit";
const SCOPE_FILL_LAYER = "epieval-boundary-scope-fill";
const HAS_DATA_FILL_LAYER = "epieval-boundary-has-data-fill";
const CHLOROPLETH_FILL_LAYER = "epieval-boundary-chloropleth-fill";
const BORDER_LAYER = "epieval-boundary-border";
const SELECTED_BORDER_LAYER = "epieval-boundary-selected-border";
const SOURCE_ID = "epieval-boundary";

// Sentinel feature-state value meaning "no data at this date / not in
// chloropleth set". Lives outside [0, 1] so the paint expression can fall
// through to transparent.
const NO_DATA = -1;

// World base — faint land fill + thin country border. Always rendered behind
// the dataset boundary so the user sees the rest of the world for context
// (otherwise US-state datasets look like floating states on the ocean).
const WORLD_BASE_SOURCE = "epieval-world-base";
const WORLD_BASE_FILL_LAYER = "epieval-world-base-fill";
const WORLD_BASE_BORDER_LAYER = "epieval-world-base-border";

function selectedFilter(id: string | null): FilterSpecification {
  return ["==", ["get", "id"], id ?? "__none__"] as FilterSpecification;
}

function setFilter(ids: ReadonlySet<string> | undefined): FilterSpecification {
  if (!ids || ids.size === 0) {
    return ["==", ["get", "id"], "__none__"] as FilterSpecification;
  }
  return ["in", ["get", "id"], ["literal", Array.from(ids)]] as FilterSpecification;
}

// scopeIds minus highlightedIds — the regions that are part of the dataset's
// declared coverage but didn't show up in the actual rows.
function scopeMissingSet(scope: ReadonlySet<string> | undefined, highlighted: ReadonlySet<string>): Set<string> {
  if (!scope) return new Set();
  const out = new Set<string>();
  for (const id of scope) if (!highlighted.has(id)) out.add(id);
  return out;
}

export function BoundaryMap({
  geojson,
  highlightedIds,
  scopeIds,
  valueByLocation,
  selected,
  onSelect,
  initialBounds
}: Props) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const mapRef = useRef<MapLibreMap | null>(null);
  const onSelectRef = useRef(onSelect);
  const highlightedRef = useRef(highlightedIds);
  const scopeRef = useRef(scopeIds);
  const geojsonRef = useRef(geojson);
  const [ready, setReady] = useState(false);

  useEffect(() => {
    onSelectRef.current = onSelect;
  }, [onSelect]);

  useEffect(() => {
    highlightedRef.current = highlightedIds;
  }, [highlightedIds]);

  useEffect(() => {
    scopeRef.current = scopeIds;
  }, [scopeIds]);

  useEffect(() => {
    geojsonRef.current = geojson;
  }, [geojson]);

  useEffect(() => {
    if (!containerRef.current || mapRef.current) return;

    const map = new maplibregl.Map({
      container: containerRef.current,
      style: mapConfig.style,
      center: mapConfig.initialCenter,
      zoom: mapConfig.initialZoom,
      minZoom: mapConfig.minZoom,
      maxZoom: mapConfig.maxZoom,
      attributionControl: { compact: true }
    });
    mapRef.current = map;
    map.addControl(new maplibregl.NavigationControl({ showCompass: false }), "top-right");

    const installLayers = () => {
      // World context — always present, behind everything else.
      if (!map.getSource(WORLD_BASE_SOURCE)) {
        map.addSource(WORLD_BASE_SOURCE, {
          type: "geojson",
          data: buildCountryBoundariesGeoJson()
        });
      }
      if (!map.getLayer(WORLD_BASE_FILL_LAYER)) {
        map.addLayer({
          id: WORLD_BASE_FILL_LAYER,
          type: "fill",
          source: WORLD_BASE_SOURCE,
          paint: { "fill-color": mapColors.land, "fill-outline-color": "rgba(0,0,0,0)" }
        });
      }
      if (!map.getLayer(WORLD_BASE_BORDER_LAYER)) {
        map.addLayer({
          id: WORLD_BASE_BORDER_LAYER,
          type: "line",
          source: WORLD_BASE_SOURCE,
          paint: { "line-color": mapColors.border, "line-width": 0.5 }
        });
      }

      // Dataset boundary — the polygons we color by data status and click on.
      if (!map.getSource(SOURCE_ID)) {
        map.addSource(SOURCE_ID, { type: "geojson", data: geojsonRef.current, promoteId: "id" });
      } else {
        (map.getSource(SOURCE_ID) as GeoJSONSource).setData(geojsonRef.current);
      }

      // Click-target fill (transparent, every region in the dataset boundary).
      if (!map.getLayer(FILL_LAYER)) {
        map.addLayer({
          id: FILL_LAYER,
          type: "fill",
          source: SOURCE_ID,
          paint: { "fill-color": "rgba(0,0,0,0)", "fill-outline-color": "rgba(0,0,0,0)" }
        });
      }
      // In-scope-but-missing fill — distinct from baseline land and from the
      // data-present red.
      if (!map.getLayer(SCOPE_FILL_LAYER)) {
        map.addLayer({
          id: SCOPE_FILL_LAYER,
          type: "fill",
          source: SOURCE_ID,
          filter: setFilter(scopeMissingSet(scopeRef.current, highlightedRef.current)),
          paint: { "fill-color": mapColors.scopeMissing, "fill-outline-color": "rgba(0,0,0,0)" }
        });
      }
      // Has-data fill — saturated red, on top. Used in binary mode (when
      // there's no per-region value to drive a chloropleth).
      if (!map.getLayer(HAS_DATA_FILL_LAYER)) {
        map.addLayer({
          id: HAS_DATA_FILL_LAYER,
          type: "fill",
          source: SOURCE_ID,
          filter: setFilter(highlightedRef.current),
          paint: { "fill-color": mapColors.hasData, "fill-outline-color": "rgba(0,0,0,0)" }
        });
      }
      // Chloropleth fill — value-driven gradient. Reads feature-state.value
      // (normalized to [0, 1] by the caller). Hidden when valueByLocation
      // isn't supplied so binary mode keeps working.
      if (!map.getLayer(CHLOROPLETH_FILL_LAYER)) {
        map.addLayer({
          id: CHLOROPLETH_FILL_LAYER,
          type: "fill",
          source: SOURCE_ID,
          paint: {
            "fill-color": [
              "case",
              ["<", ["coalesce", ["feature-state", "value"], NO_DATA], 0],
              "rgba(0,0,0,0)",
              [
                "interpolate",
                ["linear"],
                ["feature-state", "value"],
                0, "rgba(220, 38, 38, 0.10)",
                1, "rgba(220, 38, 38, 0.85)"
              ]
            ],
            "fill-outline-color": "rgba(0,0,0,0)"
          },
          layout: { visibility: "none" }
        });
      }
      // Dataset border — meaningful for sub-country views (states/counties)
      // where the world-base border doesn't cover the subdivisions.
      if (!map.getLayer(BORDER_LAYER)) {
        map.addLayer({
          id: BORDER_LAYER,
          type: "line",
          source: SOURCE_ID,
          paint: { "line-color": mapColors.border, "line-width": 0.4 }
        });
      }
      if (!map.getLayer(SELECTED_BORDER_LAYER)) {
        map.addLayer({
          id: SELECTED_BORDER_LAYER,
          type: "line",
          source: SOURCE_ID,
          filter: selectedFilter(selected?.id ?? null),
          paint: { "line-color": mapColors.selectedBorder, "line-width": 1.6 }
        });
      }

      if (initialBounds) {
        map.fitBounds(initialBounds, { padding: 24, animate: false });
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
        const props = feature.properties as BoundaryFeatureProps;
        onSelectRef.current({ id: props.id, name: props.name });
      });
    });

    return () => {
      map.remove();
      mapRef.current = null;
    };
  }, []);

  // Update geojson source when the boundary set changes (e.g. user toggles
  // from US states to US counties).
  useEffect(() => {
    if (!mapRef.current || !ready) return;
    const src = mapRef.current.getSource(SOURCE_ID) as GeoJSONSource | undefined;
    if (src) src.setData(geojson);
  }, [geojson, ready]);

  useEffect(() => {
    if (!mapRef.current || !ready) return;
    mapRef.current.setFilter(SELECTED_BORDER_LAYER, selectedFilter(selected?.id ?? null));
  }, [selected?.id, ready]);

  useEffect(() => {
    if (!mapRef.current || !ready) return;
    mapRef.current.setFilter(HAS_DATA_FILL_LAYER, setFilter(highlightedIds));
    mapRef.current.setFilter(SCOPE_FILL_LAYER, setFilter(scopeMissingSet(scopeIds, highlightedIds)));
  }, [highlightedIds, scopeIds, ready]);

  // Chloropleth mode toggle. When valueByLocation is supplied, hide the
  // binary has-data fill and show the value-driven chloropleth instead.
  useEffect(() => {
    if (!mapRef.current || !ready) return;
    const chloroplethActive = !!valueByLocation;
    mapRef.current.setLayoutProperty(
      HAS_DATA_FILL_LAYER,
      "visibility",
      chloroplethActive ? "none" : "visible"
    );
    mapRef.current.setLayoutProperty(
      CHLOROPLETH_FILL_LAYER,
      "visibility",
      chloroplethActive ? "visible" : "none"
    );
  }, [valueByLocation, ready]);

  // Push values into feature-state on every change. We write -1 (NO_DATA)
  // for features absent from the value map so the paint expression fades
  // them out instead of leaving a stale color from the previous tick.
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !ready || !valueByLocation) return;
    for (const f of geojson.features) {
      const id = f.properties.id;
      const v = valueByLocation.get(id);
      map.setFeatureState({ source: SOURCE_ID, id }, { value: v ?? NO_DATA });
    }
  }, [valueByLocation, geojson, ready]);

  const reset = () => {
    if (initialBounds) {
      mapRef.current?.fitBounds(initialBounds, { padding: 24, duration: 600 });
    } else {
      mapRef.current?.flyTo({
        center: mapConfig.initialCenter,
        zoom: mapConfig.initialZoom,
        speed: 1.4,
        essential: true
      });
    }
  };

  return (
    <div className="relative h-full min-h-[480px] overflow-hidden rounded-xl border border-white/10 bg-black">
      <div ref={containerRef} className="h-full min-h-[480px] w-full" aria-label="Boundary map" />
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
