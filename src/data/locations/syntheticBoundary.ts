// Synthetic location_id → real boundary mapping.
//
// Several EPI-Eval datasets publish location_ids that don't correspond to
// any standard polygon (HHS regions, RESP-NET catchments, MetroCast-style
// metros). Rather than vendoring custom polygons, we map each synthetic
// code to one or more *real* boundaries we already render — usually the
// FIPS state(s) the synthetic geography covers — and let the chloropleth
// paint those.
//
// This is a dashboard-side mapping (display only). The data files keep the
// synthetic codes; we don't rewrite location_id at ingest. That preserves
// data semantics — `delphi-flusurv` rows still say "RESP-NET catchment in
// California" rather than lying about being whole-state numbers, and HHS
// regions stay one row each rather than expanding to one-row-per-member-state.
//
// Codes not in this map fall through to `extendWithFallbacks`, which
// synthesises a country-level rendering so the dataset still has *some* map.

export type SyntheticTarget =
  | { kind: "us-state"; fips: string }
  | { kind: "us-state-set"; fips: string[] }
  | { kind: "country"; iso2: string };

export const SYNTHETIC_BOUNDARY_MAP: Record<string, SyntheticTarget> = {
  // ── US-FLUSURV-* (RESP-NET catchments) ──
  // Each catchment paints onto its containing state. The two NY catchments
  // (Albany / Rochester) collapse onto NY's polygon — honest about the
  // sub-state grain loss, but still gives the user a map. The network-wide
  // aggregate uses the country renderer.
  "US-FLUSURV-CA":            { kind: "us-state", fips: "06" },
  "US-FLUSURV-CO":            { kind: "us-state", fips: "08" },
  "US-FLUSURV-CT":            { kind: "us-state", fips: "09" },
  "US-FLUSURV-GA":            { kind: "us-state", fips: "13" },
  "US-FLUSURV-MD":            { kind: "us-state", fips: "24" },
  "US-FLUSURV-MI":            { kind: "us-state", fips: "26" },
  "US-FLUSURV-MN":            { kind: "us-state", fips: "27" },
  "US-FLUSURV-NM":            { kind: "us-state", fips: "35" },
  "US-FLUSURV-NY-ALBANY":     { kind: "us-state", fips: "36" },
  "US-FLUSURV-NY-ROCHESTER":  { kind: "us-state", fips: "36" },
  "US-FLUSURV-OR":            { kind: "us-state", fips: "41" },
  "US-FLUSURV-TN":            { kind: "us-state", fips: "47" },
  "US-FLUSURV-UT":            { kind: "us-state", fips: "49" },
  "US-FLUSURV-ALL":           { kind: "country", iso2: "US" },

  // ── US-HHS-1 .. US-HHS-10 (HHS regions, member states) ──
  // Each region paints all its member states. A single HHS-N row's value
  // gets painted onto every state in that region (visually a contiguous
  // multi-state highlight).
  "US-HHS-1":  { kind: "us-state-set", fips: ["09", "23", "25", "33", "44", "50"] },             // CT ME MA NH RI VT
  "US-HHS-2":  { kind: "us-state-set", fips: ["34", "36", "72", "78"] },                          // NJ NY PR VI
  "US-HHS-3":  { kind: "us-state-set", fips: ["10", "11", "24", "42", "51", "54"] },              // DE DC MD PA VA WV
  "US-HHS-4":  { kind: "us-state-set", fips: ["01", "12", "13", "21", "28", "37", "45", "47"] }, // AL FL GA KY MS NC SC TN
  "US-HHS-5":  { kind: "us-state-set", fips: ["17", "18", "26", "27", "39", "55"] },              // IL IN MI MN OH WI
  "US-HHS-6":  { kind: "us-state-set", fips: ["05", "22", "35", "40", "48"] },                    // AR LA NM OK TX
  "US-HHS-7":  { kind: "us-state-set", fips: ["19", "20", "29", "31"] },                          // IA KS MO NE
  "US-HHS-8":  { kind: "us-state-set", fips: ["08", "30", "38", "46", "49", "56"] },              // CO MT ND SD UT WY
  "US-HHS-9":  { kind: "us-state-set", fips: ["04", "06", "15", "32", "60", "66", "69"] },        // AZ CA HI NV AS GU MP
  "US-HHS-10": { kind: "us-state-set", fips: ["02", "16", "41", "53"] },                          // AK ID OR WA

  // ── US-METRO-* (flu-metrocast-hub) ──
  // Most MetroCast entries are state aggregates wearing a metro prefix
  // (Maine, Texas, Virginia, ...). City-level entries (Boston, NYC, ...)
  // map to the state of the city — same sub-state collapse as FluSurv.
  // 77 entries; populated lazily as the renderer encounters them.
  "US-METRO-MAINE":          { kind: "us-state", fips: "23" },
  "US-METRO-MARYLAND":       { kind: "us-state", fips: "24" },
  "US-METRO-MASSACHUSETTS":  { kind: "us-state", fips: "25" },
  "US-METRO-MINNESOTA":      { kind: "us-state", fips: "27" },
  "US-METRO-INDIANA":        { kind: "us-state", fips: "18" },
  "US-METRO-NORTHCAROLINA":  { kind: "us-state", fips: "37" },
  "US-METRO-SOUTHCAROLINA":  { kind: "us-state", fips: "45" },
  "US-METRO-OREGON":         { kind: "us-state", fips: "41" },
  "US-METRO-VIRGINIA":       { kind: "us-state", fips: "51" },
  "US-METRO-COLORADO":       { kind: "us-state", fips: "08" },
  "US-METRO-GEORGIA":        { kind: "us-state", fips: "13" },
  "US-METRO-UTAH":           { kind: "us-state", fips: "49" },
  "US-METRO-TEXAS":          { kind: "us-state", fips: "48" },
  // City-level metros — collapse to containing state. The chloropleth
  // shows which states have MetroCast data; the per-metro names stay
  // visible in the breakdown panel.
  "US-METRO-NYC":             { kind: "us-state", fips: "36" },
  "US-METRO-ROCHESTER":       { kind: "us-state", fips: "36" },
  "US-METRO-BOSTON":          { kind: "us-state", fips: "25" },
  "US-METRO-NEWBEDFORD":      { kind: "us-state", fips: "25" },
  "US-METRO-LYNN":            { kind: "us-state", fips: "25" },
  "US-METRO-WORCESTER":       { kind: "us-state", fips: "25" },
  "US-METRO-PITTSFIELD":      { kind: "us-state", fips: "25" },
  "US-METRO-SPRINGFIELD":     { kind: "us-state", fips: "25" },
  "US-METRO-BANGOR":          { kind: "us-state", fips: "23" },
  "US-METRO-BALTIMORE":       { kind: "us-state", fips: "24" },
  "US-METRO-FREDERICK":       { kind: "us-state", fips: "24" },
  "US-METRO-HARFORD":         { kind: "us-state", fips: "24" },
  "US-METRO-MONTGOMERY":      { kind: "us-state", fips: "24" },
  "US-METRO-AUSTIN":          { kind: "us-state", fips: "48" },
  "US-METRO-DALLAS":          { kind: "us-state", fips: "48" },
  "US-METRO-HOUSTON":         { kind: "us-state", fips: "48" },
  "US-METRO-SANANTONIO":      { kind: "us-state", fips: "48" },
  "US-METRO-ELPASO":          { kind: "us-state", fips: "48" },
  "US-METRO-BEAUMONT":        { kind: "us-state", fips: "48" },
  "US-METRO-DENVER":          { kind: "us-state", fips: "08" },
  "US-METRO-COLORADOSPRINGS": { kind: "us-state", fips: "08" },
  "US-METRO-BOULDER":         { kind: "us-state", fips: "08" },
  "US-METRO-LARIMER":         { kind: "us-state", fips: "08" },
  "US-METRO-WELD":            { kind: "us-state", fips: "08" },
  "US-METRO-SALTLAKECITY":    { kind: "us-state", fips: "49" },
  "US-METRO-PROVO":           { kind: "us-state", fips: "49" },
  "US-METRO-OGDEN":           { kind: "us-state", fips: "49" },
  "US-METRO-MESA":            { kind: "us-state", fips: "49" },
  "US-METRO-PORTLAND":        { kind: "us-state", fips: "23" }, // Portland, ME
  "US-METRO-PORTLANDOR":      { kind: "us-state", fips: "41" }, // Portland, OR
  "US-METRO-EUGENE":          { kind: "us-state", fips: "41" },
  "US-METRO-MEDFORD":         { kind: "us-state", fips: "41" },
  "US-METRO-SALEM":           { kind: "us-state", fips: "41" },
  "US-METRO-DESCHUTES":       { kind: "us-state", fips: "41" },
  "US-METRO-MINNEAPOLIS":     { kind: "us-state", fips: "27" },
  "US-METRO-STPAUL":          { kind: "us-state", fips: "27" },
  "US-METRO-STCLOUD":         { kind: "us-state", fips: "27" },
  "US-METRO-DULUTH":          { kind: "us-state", fips: "27" },
  "US-METRO-INDIANAPOLIS":    { kind: "us-state", fips: "18" },
  "US-METRO-COLUMBUS":        { kind: "us-state", fips: "39" },
  "US-METRO-COLUMBIA":        { kind: "us-state", fips: "45" }, // Columbia, SC
  "US-METRO-CHARLESTON":      { kind: "us-state", fips: "45" },
  "US-METRO-FLORENCE":        { kind: "us-state", fips: "45" },
  "US-METRO-GREENVILLE":      { kind: "us-state", fips: "45" },
  "US-METRO-HORRY":           { kind: "us-state", fips: "45" },
  "US-METRO-ROCKHILL":        { kind: "us-state", fips: "45" },
  "US-METRO-CLTAREA":         { kind: "us-state", fips: "37" }, // Charlotte
  "US-METRO-RTPAREA":         { kind: "us-state", fips: "37" }, // Research Triangle
  "US-METRO-TRIADAREA":       { kind: "us-state", fips: "37" },
  "US-METRO-WNC":             { kind: "us-state", fips: "37" },
  "US-METRO-NENC":            { kind: "us-state", fips: "37" },
  "US-METRO-SENC":            { kind: "us-state", fips: "37" },
  "US-METRO-FAYAREA":         { kind: "us-state", fips: "37" },
  "US-METRO-ATHENS":          { kind: "us-state", fips: "13" }, // Athens, GA
  "US-METRO-MACON":           { kind: "us-state", fips: "13" },
  "US-METRO-MARIETTA":        { kind: "us-state", fips: "13" },
  "US-METRO-LAGRANGE":        { kind: "us-state", fips: "13" },
  "US-METRO-SOUTHAUGUSTA":    { kind: "us-state", fips: "13" },
  "US-METRO-SAVANNAH":        { kind: "us-state", fips: "13" },
  "US-METRO-CHEROKEE":        { kind: "us-state", fips: "13" },
  "US-METRO-FLOYD":           { kind: "us-state", fips: "13" },
  "US-METRO-HALL":            { kind: "us-state", fips: "13" },
  "US-METRO-HENRY":           { kind: "us-state", fips: "13" },
  "US-METRO-ROANOKE":         { kind: "us-state", fips: "51" },
};

/**
 * For a row's location_id, return the boundary id(s) it should be painted
 * onto. Returns an empty array when the code isn't in the registry — the
 * caller treats that as "skip this row at this rendering."
 */
export function expandSyntheticToBoundaryIds(
  locationId: string,
  targetKind: "us-state" | "country"
): string[] {
  const target = SYNTHETIC_BOUNDARY_MAP[locationId];
  if (!target) return [];
  if (targetKind === "us-state") {
    if (target.kind === "us-state") return [target.fips];
    if (target.kind === "us-state-set") return target.fips;
    return []; // country target can't be rendered at us-state grain
  }
  // country target kind
  if (target.kind === "country") return [target.iso2];
  return [];
}

/**
 * Decide what target boundary kind to render the level at, given the codes
 * present. Granularity wins on ties: if any code maps to a us-state /
 * us-state-set, render at us-state level — country-target codes (like the
 * FluSurv network-wide aggregate `US-FLUSURV-ALL`) and any unmapped codes
 * are silently dropped from the highlighted set; the user can pick the
 * country-aggregated fallback level (synthesised by `extendWithFallbacks`)
 * to see them.
 *
 * Returns null only when *no* code in the level resolves to a known
 * boundary — caller treats that as "render nothing at this level."
 */
export function pickSyntheticTargetKind(
  ids: ReadonlySet<string>
): "us-state" | "country" | null {
  if (ids.size === 0) return null;
  let hasUsLike = false;
  let hasCountry = false;
  let hasMapped = false;
  for (const id of ids) {
    const t = SYNTHETIC_BOUNDARY_MAP[id];
    if (!t) continue; // unmapped codes drop out, but don't bail the whole level
    hasMapped = true;
    if (t.kind === "us-state" || t.kind === "us-state-set") hasUsLike = true;
    else if (t.kind === "country") hasCountry = true;
  }
  if (!hasMapped) return null;
  if (hasUsLike) return "us-state"; // granularity wins
  if (hasCountry) return "country";
  return null;
}
