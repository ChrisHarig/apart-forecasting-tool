import type { StyleSpecification } from "maplibre-gl";

export const DEFAULT_MAP_STYLE_URL = "https://tiles.openfreemap.org/styles/positron";

export const fallbackBoundaryStyle: StyleSpecification = {
  version: 8,
  name: "Sentinel Atlas boundary fallback",
  sources: {},
  layers: [
    {
      id: "sentinel-fallback-background",
      type: "background",
      paint: {
        "background-color": "#050505"
      }
    }
  ]
};

export const mapConfig = {
  styleUrl: import.meta.env.VITE_MAP_STYLE_URL || DEFAULT_MAP_STYLE_URL,
  fallbackStyle: fallbackBoundaryStyle,
  styleLoadTimeoutMs: 3500,
  initialCenter: [10, 20] as [number, number],
  initialZoom: 1.25,
  minZoom: 1,
  maxZoom: 16
};
