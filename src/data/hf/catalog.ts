import type { SourceMetadata, SurveillanceCategory, ValueColumn, ValueType } from "../../types/source";
import { listOrgDatasets, type HfDatasetInfo } from "./client";
import { readCache, writeCache } from "./cache";

const CATALOG_KEY = "catalog";

const KNOWN_CATEGORIES: SurveillanceCategory[] = [
  "respiratory",
  "arboviral",
  "enteric",
  "mortality",
  "mobility",
  "search",
  "genomic",
  "notifiable",
  "none"
];

const KNOWN_VALUE_TYPES: ValueType[] = [
  "incident",
  "cumulative",
  "stock",
  "rate",
  "proportion",
  "index",
  "count",
  "other"
];

function asString(v: unknown): string | undefined {
  return typeof v === "string" && v.length > 0 ? v : undefined;
}

function asStringArray(v: unknown): string[] {
  return Array.isArray(v) ? v.filter((x): x is string => typeof x === "string") : [];
}

function asTier(v: unknown): 1 | 2 | 3 | undefined {
  const n = typeof v === "number" ? v : Number(v);
  return n === 1 || n === 2 || n === 3 ? n : undefined;
}

function asCategory(v: unknown): SurveillanceCategory {
  const s = asString(v);
  return (s && (KNOWN_CATEGORIES as string[]).includes(s) ? s : "none") as SurveillanceCategory;
}

function asValueColumns(v: unknown): ValueColumn[] {
  if (!Array.isArray(v)) return [];
  return v
    .map((entry): ValueColumn | null => {
      if (!entry || typeof entry !== "object") return null;
      const e = entry as Record<string, unknown>;
      const name = asString(e.name);
      if (!name) return null;
      const dtype = asString(e.dtype);
      const value_type = asString(e.value_type);
      return {
        name,
        dtype: (dtype === "int" || dtype === "float" || dtype === "str" || dtype === "category" ? dtype : "float"),
        unit: asString(e.unit),
        value_type:
          value_type && (KNOWN_VALUE_TYPES as string[]).includes(value_type)
            ? (value_type as ValueType)
            : undefined,
        description: asString(e.description),
        aggregation: asString(e.aggregation) as ValueColumn["aggregation"] | undefined
      };
    })
    .filter((x): x is ValueColumn => x !== null);
}

function deriveSourceFromHf(info: HfDatasetInfo): SourceMetadata {
  const card = (info.cardData ?? {}) as Record<string, unknown>;
  const computed = (card.computed as Record<string, unknown> | undefined) ?? undefined;
  const notes = (card.notes as Record<string, unknown> | undefined) ?? undefined;
  const sourceIdSlug = asString(card.source_id) ?? info.id.split("/").pop() ?? info.id;

  return {
    id: info.id,
    pretty_name: asString(card.pretty_name) ?? sourceIdSlug,
    source_id: sourceIdSlug,
    source_url: asString(card.source_url),
    manifest_section: asString(card.manifest_section),
    description: asString(card.description) ?? asString(notes?.general),
    surveillance_category: asCategory(card.surveillance_category),
    pathogens: asStringArray(card.pathogens),
    cadence: asString(card.cadence),
    geography_levels: asStringArray(card.geography_levels),
    geography_countries: asStringArray(card.geography_countries),
    tier: asTier(card.tier),
    availability: asString(card.availability),
    access_type: asString(card.access_type),
    value_columns: asValueColumns(card.value_columns),
    computed: computed
      ? {
          last_ingested: asString(computed.last_ingested),
          row_count: typeof computed.row_count === "number" ? computed.row_count : undefined,
          time_coverage: Array.isArray(computed.time_coverage)
            ? computed.time_coverage
                .map((entry) => {
                  const e = entry as Record<string, unknown> | undefined;
                  const start = asString(e?.start);
                  const end = asString(e?.end);
                  return start && end ? { start, end } : null;
                })
                .filter((x): x is { start: string; end: string } => x !== null)
            : undefined,
          geography_unit_count:
            typeof computed.geography_unit_count === "number" ? computed.geography_unit_count : undefined,
          observed_cadence_days:
            typeof computed.observed_cadence_days === "number" ? computed.observed_cadence_days : undefined
        }
      : undefined,
    notes_general: asString(notes?.general),
    last_modified: info.lastModified
  };
}

export async function getCatalog(opts: { force?: boolean } = {}): Promise<SourceMetadata[]> {
  if (!opts.force) {
    const cached = readCache<SourceMetadata[]>(CATALOG_KEY);
    if (cached) return cached;
  }
  const datasets = await listOrgDatasets();
  const catalog = datasets.map(deriveSourceFromHf).sort((a, b) => a.pretty_name.localeCompare(b.pretty_name));
  writeCache(CATALOG_KEY, catalog);
  return catalog;
}

export const _internal = { deriveSourceFromHf };
