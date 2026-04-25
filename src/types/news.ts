export type NewsSignalSeverity = "info" | "watch" | "elevated" | "unknown";
export type NewsSourceProvenance = "official" | "trusted_media" | "aggregator" | "user_added" | "unknown";

export interface CountryNewsItem {
  id: string;
  headline: string;
  date: string;
  source: string;
  countryIso3: string;
  countryName: string;
  relatedSignal?: string;
  severity: NewsSignalSeverity;
  confidenceStatus: "unverified" | "source_reported" | "verified" | "unknown";
  provenance: NewsSourceProvenance;
  url?: string;
}

export interface CountryNewsSummary {
  countryIso3: string;
  status: "idle" | "loading" | "ready" | "error";
  items: CountryNewsItem[];
  error?: string;
  updatedAt?: string;
}
