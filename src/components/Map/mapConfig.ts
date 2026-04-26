import type { StyleSpecification } from "maplibre-gl";

// Self-contained ocean-only style. The "land" is provided by whichever
// boundary GeoJSON the BoundaryMap renders on top — countries / US states /
// US counties — so the political map looks the same regardless of zoom and
// no terrain or roads ever show up.
export const minimalDarkStyle: StyleSpecification = {
  version: 8,
  name: "EPI-Eval ocean",
  sources: {},
  layers: [
    {
      id: "ocean",
      type: "background",
      paint: { "background-color": "#0b1422" }
    }
  ]
};

// Color tokens used by BoundaryMap. Centralized so #2's "scope but missing"
// distinction reads consistently and so we can theme everything in one place.
export const mapColors = {
  ocean: "#0b1422",
  land: "rgba(255, 255, 255, 0.06)",        // baseline land (anything not in scope)
  scopeMissing: "rgba(255, 255, 255, 0.18)", // in scope, no data — a clear gray
  hasData: "rgba(220, 38, 38, 0.42)",         // data present — saturated red
  border: "rgba(255, 255, 255, 0.22)",        // thin land border
  selectedBorder: "#ef4444"
};

export const mapConfig = {
  // External map override is still possible via env. Default is the inline
  // ocean-only style — no tile fetch, no terrain, deterministic.
  style: (import.meta.env.VITE_MAP_STYLE_URL as string | undefined) || minimalDarkStyle,
  styleLoadTimeoutMs: 3500,
  initialCenter: [10, 20] as [number, number],
  initialZoom: 1.4,
  minZoom: 0,
  maxZoom: 20
};
