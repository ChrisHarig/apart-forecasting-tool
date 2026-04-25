import type { SourceCategory } from "../../types/source";

export type SourceCategoryTone = "red" | "redSoft" | "light" | "neutral";

export interface SourceCategoryOption {
  id: SourceCategory;
  label: string;
  description: string;
  tone: SourceCategoryTone;
}

export const sourceCategoryLabels: Record<SourceCategory, string> = {
  pathogen_surveillance: "Pathogen surveillance",
  wastewater: "Wastewater",
  forecasts_nowcasts: "Forecasts / nowcasts",
  mobility_air_travel: "Mobility / air travel",
  ports_maritime_cargo: "Ports / maritime / cargo",
  population_demographics: "Population / demographics",
  news_event_surveillance: "Open-source news / event surveillance",
  user_added: "User-added sources"
};

export const orderedSourceCategories: SourceCategory[] = [
  "pathogen_surveillance",
  "wastewater",
  "forecasts_nowcasts",
  "mobility_air_travel",
  "ports_maritime_cargo",
  "population_demographics",
  "news_event_surveillance",
  "user_added"
];

const sourceCategoryDescriptions: Record<SourceCategory, string> = {
  pathogen_surveillance: "Country or jurisdiction-level clinical and laboratory surveillance.",
  wastewater: "Aggregate wastewater and sewershed surveillance signals.",
  forecasts_nowcasts: "Model outputs, nowcasts, forecast hubs, and uncertainty references.",
  mobility_air_travel: "Privacy-preserving mobility and aggregate air travel context.",
  ports_maritime_cargo: "Port, maritime, cargo, and route activity aggregated for context.",
  population_demographics: "Population, density, and demographic context layers.",
  news_event_surveillance: "Curated country-level public-health event summaries.",
  user_added: "Locally stored sources awaiting validation."
};

const sourceCategoryTones: Record<SourceCategory, SourceCategoryOption["tone"]> = {
  pathogen_surveillance: "light",
  wastewater: "red",
  forecasts_nowcasts: "redSoft",
  mobility_air_travel: "redSoft",
  ports_maritime_cargo: "redSoft",
  population_demographics: "neutral",
  news_event_surveillance: "red",
  user_added: "neutral"
};

export const sourceCategories: SourceCategoryOption[] = orderedSourceCategories.map((category) => ({
  id: category,
  label: sourceCategoryLabels[category],
  description: sourceCategoryDescriptions[category],
  tone: sourceCategoryTones[category]
}));

export const sourceCategoryById: Record<SourceCategory, SourceCategoryOption> = Object.fromEntries(
  sourceCategories.map((category) => [category.id, category])
) as Record<SourceCategory, SourceCategoryOption>;
