import type { StyleSpecification } from "maplibre-gl";

// Liberty has more detail than positron; falls back gracefully.
export const DEFAULT_MAP_STYLE_URL = "https://tiles.openfreemap.org/styles/liberty";

export const fallbackBoundaryStyle: StyleSpecification = {
  version: 8,
  name: "EPI-Eval boundary fallback",
  sources: {},
  layers: [
    {
      id: "epieval-fallback-background",
      type: "background",
      paint: { "background-color": "#050505" }
    }
  ]
};

export const mapConfig = {
  styleUrl: import.meta.env.VITE_MAP_STYLE_URL || DEFAULT_MAP_STYLE_URL,
  fallbackStyle: fallbackBoundaryStyle,
  styleLoadTimeoutMs: 3500,
  initialCenter: [10, 20] as [number, number],
  initialZoom: 1.4,
  minZoom: 0,
  maxZoom: 20
};
