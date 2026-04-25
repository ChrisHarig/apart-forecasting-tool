export type SourceCategory =
  | "pathogen_surveillance"
  | "wastewater"
  | "forecasts_nowcasts"
  | "mobility_air_travel"
  | "ports_maritime_cargo"
  | "population_demographics"
  | "news_event_surveillance"
  | "user_added";

export type SourceCategoryId = SourceCategory;

export type SourceAccessType =
  | "public_api"
  | "downloadable_file"
  | "dashboard_only"
  | "user_upload"
  | "backend_required"
  | "unknown";

export type SourceAdapterStatus = "ready" | "partial" | "placeholder" | "backend_required" | "unavailable";
export type LegacySourceMvpStatus = "include now" | "placeholder" | "later";
export type SourceMvpStatus = LegacySourceMvpStatus | "keep" | "add" | "user_added";
export type CountryAvailability = "available" | "unavailable" | "unknown" | "global_source_unknown_country_filter";

export type SourceCountryCoverageStatus = "available" | "candidate" | "planned" | "unknown";

export type SourceCountryGranularity =
  | "global"
  | "country"
  | "admin1"
  | "admin2"
  | "site"
  | "network"
  | "point"
  | "route-aggregate"
  | "grid";

export interface SourceCountryCoverage {
  iso3: string;
  isoNumeric?: string;
  countryName: string;
  status: SourceCountryCoverageStatus;
  granularity: SourceCountryGranularity;
  notes?: string;
}

export interface DataSourceMetadata {
  id: string;
  name: string;
  category: SourceCategory;
  description: string;
  officialUrl: string;
  owner: string;
  geographicCoverage: string;
  supportedCountries: string[];
  granularity: string;
  temporalResolution: string;
  updateCadence: string;
  likelyFields: string[];
  fileFormats: string[];
  accessType: SourceAccessType;
  licenseNotes: string;
  provenanceNotes: string;
  dataQualityNotes: string;
  limitations: string;
  adapterStatus: SourceAdapterStatus;
  mvpStatus: SourceMvpStatus;
  countryAvailability: CountryAvailability;
  lastVerifiedDate: string;
  userAdded: boolean;
  sourceName?: string;
  dataType?: string;
  pathogenOrSignalCoverage?: string;
  geographyGranularity?: string;
  relevance?: string;
  countryCoverage?: SourceCountryCoverage[];
  validationStatus?: "public metadata reviewed" | "adapter candidate" | "needs schema review" | "not validated";
  privacyClassification?: "aggregate public" | "aggregate restricted" | "sensitive aggregate" | "reject individual-level";
  aggregateOnly?: boolean;
  warnings?: string[];
  createdAt?: string;
  updatedAt?: string;
  notes?: string;
}

export type SourceMetadata = DataSourceMetadata;

export interface CatalogSourceMetadata extends Omit<DataSourceMetadata, "mvpStatus"> {
  sourceName: string;
  dataType: string;
  pathogenOrSignalCoverage: string;
  geographyGranularity: string;
  relevance: string;
  countryCoverage: SourceCountryCoverage[];
  mvpStatus: LegacySourceMvpStatus;
}

export interface AddSourceInput {
  name: string;
  url: string;
  category: SourceCategory;
  countries: string[];
  dataType: string;
  updateCadence: string;
  notes: string;
}

export interface UserSourceInput {
  sourceName: string;
  category: SourceCategory;
  dataType: string;
  pathogenOrSignalCoverage: string;
  geographyGranularity: string;
  countryCoverage: SourceCountryCoverage[];
  updateCadence: string;
  likelyFields: string;
  relevance: string;
  limitations: string;
  sourceUrl?: string;
  maintainer?: string;
  notes?: string;
}

export interface SourceValidationResult {
  ok: boolean;
  valid: boolean;
  errors: string[];
  warnings: string[];
}

export interface SourceRegistrySnapshot {
  builtInSources: DataSourceMetadata[];
  userSources: DataSourceMetadata[];
  allSources: DataSourceMetadata[];
}
