// Aligned with the EPI-Eval card schema (upload_pipeline/schema/schema_v0.1.md).
// This is what we get back from HF's /api/datasets cardData for an EPI-Eval dataset.

export type SurveillanceCategory =
  | "respiratory"
  | "arboviral"
  | "enteric"
  | "mortality"
  | "mobility"
  | "search"
  | "genomic"
  | "notifiable"
  | "none";

export type ValueType =
  | "incident"
  | "cumulative"
  | "stock"
  | "rate"
  | "proportion"
  | "index"
  | "count"
  | "other";

export interface ValueColumn {
  name: string;
  dtype: "int" | "float" | "str" | "category";
  unit?: string;
  value_type?: ValueType;
  description?: string;
  aggregation?: "sum" | "mean" | "rate" | "proportion" | "count" | "max" | "none";
}

export interface TimeCoverageInterval {
  start: string;
  end: string | "present";
}

export interface ComputedMetadata {
  last_ingested?: string;
  row_count?: number;
  time_coverage?: TimeCoverageInterval[];
  geography_unit_count?: number;
  observed_cadence_days?: number;
}

export interface SourceMetadata {
  id: string;
  pretty_name: string;
  source_id: string;
  source_url?: string;
  manifest_section?: string;
  description?: string;
  surveillance_category: SurveillanceCategory;
  pathogens: string[];
  cadence?: string;
  geography_levels: string[];
  geography_countries: string[];
  tier?: 1 | 2 | 3;
  availability?: string;
  access_type?: string;
  value_columns: ValueColumn[];
  computed?: ComputedMetadata;
  notes_general?: string;
  last_modified?: string;
}
