import { sourceCatalog } from "../sources/sourceCatalog";
import type {
  AddSourceInput,
  DataSourceMetadata,
  SourceCountryCoverage,
  SourceRegistrySnapshot,
  SourceValidationResult,
  UserSourceInput
} from "../../types/source";
import { normalizeIso3 } from "../../utils/countryCodes";
import { readJsonFromLocalStorage, writeJsonToLocalStorage } from "../../utils/localStorage";

const USER_SOURCES_KEY = "sentinel-atlas:user-sources";
const sensitiveTerms = [
  "individual",
  "person-level",
  "patient record",
  "medical record",
  "medical-record",
  "patient_id",
  "medical_record_number",
  "mrn",
  "pii",
  "ssn",
  "phone",
  "email",
  "device id",
  "device_id",
  "home address",
  "precise gps",
  "gps trace",
  "personal mobility",
  "trace-level",
  "contact tracing"
];
const operationalWarningTerms = ["flight-level", "vessel-level", "vehicle-level", "callsign", "tail number", "ship id", "ais message", "raw trajectory"];

export function validateSourceInput(input: AddSourceInput): SourceValidationResult {
  const errors: string[] = [];
  const warnings: string[] = [];
  const combinedText = `${input.name} ${input.dataType} ${input.notes}`.toLowerCase();

  if (!input.name.trim()) errors.push("Source name is required.");
  if (!input.url.trim()) errors.push("Source URL is required.");
  if (input.url.trim() && !/^https?:\/\/|^\//i.test(input.url.trim())) {
    errors.push("Source URL must start with http://, https://, or / for a future backend route.");
  }
  if (input.countries.length === 0) errors.push("Add at least one country or GLOBAL coverage.");

  const matchedSensitiveTerm = sensitiveTerms.find((term) => combinedText.includes(term));
  if (matchedSensitiveTerm) {
    errors.push(`This dashboard only accepts aggregate data. Remove individual-level or sensitive content references such as "${matchedSensitiveTerm}".`);
  }

  const matchedOperationalTerm = operationalWarningTerms.find((term) => combinedText.includes(term));
  if (matchedOperationalTerm) {
    warnings.push(`Aggregate operational detail before display; review sensitive term "${matchedOperationalTerm}".`);
  }

  if (!/\b(aggregate|country|national|state|province|region|weekly|monthly|site|sewershed|index|rate|count|summary|grid|route)\b/i.test(combinedText)) {
    warnings.push("Describe the source as aggregate, country-level, site-level, or indexed before connecting it.");
  }

  if (input.category === "user_added") {
    warnings.push("User-added sources are stored locally and are not validated by Sentinel Atlas.");
  }

  return { ok: errors.length === 0, valid: errors.length === 0, errors, warnings };
}

export function normalizeCoverageCountries(rawCountries: string[]): string[] {
  return [...new Set(rawCountries.map((country) => (country.toUpperCase() === "GLOBAL" ? "GLOBAL" : normalizeIso3(country))).filter(Boolean) as string[])];
}

export function createUserSource(input: AddSourceInput): DataSourceMetadata {
  const now = new Date().toISOString();
  const countries = normalizeCoverageCountries(input.countries);
  const sourceName = input.name.trim();
  const dataType = input.dataType.trim() || "User-added aggregate source.";
  const countryCoverage: SourceCountryCoverage[] = countries.map((iso3) => ({
    iso3,
    countryName: iso3 === "GLOBAL" ? "Global" : iso3,
    status: "unknown",
    granularity: iso3 === "GLOBAL" ? "global" : "country",
    notes: "User-added coverage metadata; not validated."
  }));

  return {
    id: `user-${Date.now()}`,
    name: sourceName,
    category: input.category === "user_added" ? "user_added" : input.category,
    description: dataType,
    officialUrl: input.url.trim(),
    owner: "User added / not validated",
    geographicCoverage: countries.includes("GLOBAL") ? "Global or multi-country" : countries.join(", "),
    supportedCountries: countries,
    granularity: "User supplied",
    temporalResolution: "User supplied",
    updateCadence: input.updateCadence.trim() || "Unknown",
    likelyFields: ["date", "metric", "value", "countryIso3"],
    fileFormats: ["CSV", "JSON"],
    accessType: "user_upload",
    licenseNotes: "User must verify rights and license before operational use.",
    provenanceNotes: "User added / not validated.",
    dataQualityNotes: "No validation beyond frontend metadata checks.",
    limitations: input.notes.trim() || "Not verified by Sentinel Atlas.",
    adapterStatus: "placeholder",
    mvpStatus: "user_added",
    countryAvailability: countries.length > 0 ? "available" : "unknown",
    lastVerifiedDate: now.slice(0, 10),
    userAdded: true,
    sourceName,
    dataType,
    pathogenOrSignalCoverage: "User-supplied aggregate source metadata",
    geographyGranularity: countries.includes("GLOBAL") ? "Global or multi-country" : "Country-level metadata",
    relevance: input.notes.trim() || "User-added source candidate for future adapter review.",
    countryCoverage,
    validationStatus: "not validated",
    privacyClassification: "aggregate restricted",
    aggregateOnly: true,
    warnings: ["User-added sources are not validated and are not connected to live adapters."],
    createdAt: now,
    updatedAt: now,
    notes: input.notes.trim()
  };
}

export const sourceRegistryAdapter = {
  listBaseSources(): DataSourceMetadata[] {
    return sourceCatalog;
  },

  loadUserSources(): DataSourceMetadata[] {
    return readJsonFromLocalStorage<DataSourceMetadata[]>(USER_SOURCES_KEY, []);
  },

  saveUserSources(sources: DataSourceMetadata[]): void {
    writeJsonToLocalStorage(USER_SOURCES_KEY, sources);
  },

  listAllSources(): DataSourceMetadata[] {
    return [...sourceCatalog, ...this.loadUserSources()];
  },

  addUserSource(input: AddSourceInput): { source?: DataSourceMetadata; validation: SourceValidationResult } {
    const normalizedInput = { ...input, countries: normalizeCoverageCountries(input.countries) };
    const validation = validateSourceInput(normalizedInput);
    if (!validation.valid) return { validation };
    const source = createUserSource(normalizedInput);
    const next = [...this.loadUserSources(), source];
    this.saveUserSources(next);
    return { source, validation };
  },

  getSnapshot(): SourceRegistrySnapshot {
    const userSources = this.loadUserSources();
    return {
      builtInSources: sourceCatalog,
      userSources,
      allSources: [...sourceCatalog, ...userSources]
    };
  },

  removeUserSource(sourceId: string): SourceRegistrySnapshot {
    const next = this.loadUserSources().filter((source) => source.id !== sourceId);
    this.saveUserSources(next);
    return {
      builtInSources: sourceCatalog,
      userSources: next,
      allSources: [...sourceCatalog, ...next]
    };
  },

  clearUserSources(): SourceRegistrySnapshot {
    this.saveUserSources([]);
    return {
      builtInSources: sourceCatalog,
      userSources: [],
      allSources: [...sourceCatalog]
    };
  }
};

export type SourceRegistryAdapter = typeof sourceRegistryAdapter;

function userSourceInputToAddSourceInput(input: UserSourceInput): AddSourceInput {
  return {
    name: input.sourceName,
    url: input.sourceUrl ?? "",
    category: input.category,
    countries: input.countryCoverage.map((coverage) => coverage.iso3),
    dataType: input.dataType,
    updateCadence: input.updateCadence,
    notes: [input.pathogenOrSignalCoverage, input.geographyGranularity, input.relevance, input.limitations, input.notes]
      .filter(Boolean)
      .join(" ")
  };
}

export function validateUserSourceInput(input: UserSourceInput): SourceValidationResult {
  return validateSourceInput(userSourceInputToAddSourceInput(input));
}

export function createUserSourceMetadata(
  input: UserSourceInput,
  existingSources: DataSourceMetadata[] = sourceCatalog
): { source: DataSourceMetadata | null; validation: SourceValidationResult; snapshot: SourceRegistrySnapshot } {
  const validation = validateUserSourceInput(input);
  if (!validation.valid) {
    return {
      source: null,
      validation,
      snapshot: {
        builtInSources: existingSources,
        userSources: [],
        allSources: existingSources
      }
    };
  }

  const source = createUserSource(userSourceInputToAddSourceInput(input));
  return {
    source,
    validation,
    snapshot: {
      builtInSources: existingSources,
      userSources: [source],
      allSources: [...existingSources, source]
    }
  };
}

export function sourceSupportsCountry(source: DataSourceMetadata, iso3: string | null): boolean {
  if (!iso3) return false;
  if (source.supportedCountries.includes("GLOBAL")) return true;
  return source.supportedCountries.includes(iso3);
}

export function getSourcesForCountry(sources: DataSourceMetadata[], iso3: string | null): DataSourceMetadata[] {
  if (!iso3) return [];
  return sources.filter((source) => sourceSupportsCountry(source, iso3));
}
