import { sourceCategoryLabels } from "./sourceCategories";
import type {
  CatalogSourceMetadata,
  DataSourceMetadata,
  LegacySourceMvpStatus,
  SourceCountryCoverage,
  SourceCountryGranularity,
  SourceCountryCoverageStatus
} from "../../types/source";

const verified = "2026-04-25";

const sourceCatalogRecords: DataSourceMetadata[] = [
  {
    id: "wastewaterscan",
    name: "WastewaterSCAN",
    category: "wastewater",
    description: "Wastewater monitoring network for respiratory and enteric targets where participating sites report.",
    officialUrl: "https://data.wastewaterscan.org/",
    owner: "WastewaterSCAN",
    geographicCoverage: "Primarily United States participating sewersheds",
    supportedCountries: ["USA"],
    granularity: "Site, sewershed, metro aggregation",
    temporalResolution: "Sample date",
    updateCadence: "Varies by site",
    likelyFields: ["site_id", "sample_date", "target", "normalized_concentration", "trend", "quality_flag"],
    fileFormats: ["dashboard", "CSV/API TBD"],
    accessType: "dashboard_only",
    licenseNotes: "Confirm terms before production ingestion.",
    provenanceNotes: "Use only aggregate sewershed-level metrics.",
    dataQualityNotes: "Coverage and reporting lag vary by catchment.",
    limitations: "Not all sites report all targets; method and normalization details must be preserved.",
    adapterStatus: "placeholder",
    mvpStatus: "keep",
    countryAvailability: "available",
    lastVerifiedDate: verified,
    userAdded: false
  },
  {
    id: "cdc-flusight-current",
    name: "CDC FluSight current-week visualization",
    category: "forecasts_nowcasts",
    description: "CDC visualization reference for current-week influenza forecast and nowcast communication.",
    officialUrl: "https://www.cdc.gov/flu/weekly/flusight/",
    owner: "CDC",
    geographicCoverage: "United States",
    supportedCountries: ["USA"],
    granularity: "National and jurisdiction-level views where available",
    temporalResolution: "Weekly",
    updateCadence: "Weekly when active",
    likelyFields: ["reference_date", "target_week", "location", "quantile", "model_output"],
    fileFormats: ["dashboard", "CSV/API TBD"],
    accessType: "dashboard_only",
    licenseNotes: "Public-health government source; verify specific endpoint terms.",
    provenanceNotes: "Use as a forecast communication reference until direct data adapter exists.",
    dataQualityNotes: "Forecast challenge scope and targets vary by season.",
    limitations: "Dashboard view is not a stable ingestion API.",
    adapterStatus: "placeholder",
    mvpStatus: "keep",
    countryAvailability: "available",
    lastVerifiedDate: verified,
    userAdded: false
  },
  {
    id: "cdc-flusight-hub",
    name: "CDC FluSight Forecast Hub",
    category: "forecasts_nowcasts",
    description: "Forecast Hub repository containing influenza challenge submissions and truth data.",
    officialUrl: "https://github.com/cdcepi/FluSight-forecast-hub",
    owner: "CDC / Forecast Hub contributors",
    geographicCoverage: "United States",
    supportedCountries: ["USA"],
    granularity: "National and state-level targets depending on season",
    temporalResolution: "Weekly",
    updateCadence: "Weekly during challenge periods",
    likelyFields: ["model_id", "reference_date", "target", "horizon", "quantile", "location"],
    fileFormats: ["CSV", "parquet", "GitHub repository"],
    accessType: "downloadable_file",
    licenseNotes: "Confirm repository license and attribution before production use.",
    provenanceNotes: "Model submissions require model identity and reference-date handling.",
    dataQualityNotes: "Challenge schemas and target definitions can change over time.",
    limitations: "Respiratory forecast use case only; not a generalized pandemic feed.",
    adapterStatus: "partial",
    mvpStatus: "keep",
    countryAvailability: "available",
    lastVerifiedDate: verified,
    userAdded: false
  },
  {
    id: "reich-lab-flusight",
    name: "Reich Lab FluSight dashboard",
    category: "forecasts_nowcasts",
    description: "Forecast visualization reference for FluSight-style uncertainty and model comparison.",
    officialUrl: "https://reichlab.io/flusight-dashboard/",
    owner: "Reich Lab",
    geographicCoverage: "United States",
    supportedCountries: ["USA"],
    granularity: "National and state-level where available",
    temporalResolution: "Weekly",
    updateCadence: "Weekly during active periods",
    likelyFields: ["forecast_date", "target", "location", "observed_value", "forecast_quantile"],
    fileFormats: ["dashboard", "GitHub/data endpoints TBD"],
    accessType: "dashboard_only",
    licenseNotes: "Confirm before direct dashboard extraction.",
    provenanceNotes: "Useful reference for visual design and uncertainty communication.",
    dataQualityNotes: "Underlying challenge data should be ingested from official hubs where possible.",
    limitations: "Not treated as a live data feed in the MVP.",
    adapterStatus: "placeholder",
    mvpStatus: "keep",
    countryAvailability: "available",
    lastVerifiedDate: verified,
    userAdded: false
  },
  {
    id: "cdc-nwss",
    name: "CDC NWSS / wastewater program",
    category: "wastewater",
    description: "CDC National Wastewater Surveillance System public wastewater program and viral activity metrics.",
    officialUrl: "https://www.cdc.gov/nwss/",
    owner: "CDC",
    geographicCoverage: "United States",
    supportedCountries: ["USA"],
    granularity: "Site, county, state, regional summaries where available",
    temporalResolution: "Sample date / reporting week",
    updateCadence: "TBD by endpoint and jurisdiction",
    likelyFields: ["sample_date", "site", "location", "percentile", "trend", "viral_activity_level"],
    fileFormats: ["dashboard", "CSV/API TBD"],
    accessType: "dashboard_only",
    licenseNotes: "Public CDC source; verify endpoint terms before adapter work.",
    provenanceNotes: "Primary U.S. wastewater source candidate.",
    dataQualityNotes: "Public views may be transformed, delayed, or suppressed for coverage reasons.",
    limitations: "Not all sites report all targets; historical comparability can vary.",
    adapterStatus: "placeholder",
    mvpStatus: "keep",
    countryAvailability: "available",
    lastVerifiedDate: verified,
    userAdded: false
  },
  {
    id: "who-flunet",
    name: "WHO FluNet",
    category: "pathogen_surveillance",
    description: "Country-level influenza virological surveillance reports.",
    officialUrl: "https://www.who.int/tools/flunet",
    owner: "World Health Organization",
    geographicCoverage: "Global country-level reporting",
    supportedCountries: ["GLOBAL"],
    granularity: "Country and week",
    temporalResolution: "Weekly",
    updateCadence: "Weekly with reporting delays",
    likelyFields: ["country", "week", "specimens_processed", "positive_counts", "subtype"],
    fileFormats: ["dashboard", "CSV/API TBD"],
    accessType: "public_api",
    licenseNotes: "Verify WHO terms and attribution before production use.",
    provenanceNotes: "Use with clear reporting-delay and completeness metadata.",
    dataQualityNotes: "Reporting completeness varies by country and week.",
    limitations: "Influenza-specific; not comprehensive for all pathogen surveillance.",
    adapterStatus: "placeholder",
    mvpStatus: "keep",
    countryAvailability: "global_source_unknown_country_filter",
    lastVerifiedDate: verified,
    userAdded: false
  },
  {
    id: "opensky",
    name: "OpenSky Network",
    category: "mobility_air_travel",
    description: "Aircraft movement data source candidate for aggregate airport movement context.",
    officialUrl: "https://opensky-network.org/",
    owner: "OpenSky Network",
    geographicCoverage: "Global ADS-B coverage with regional gaps",
    supportedCountries: ["GLOBAL"],
    granularity: "Flight or airport-derived aggregates after privacy-preserving processing",
    temporalResolution: "Near-real-time / historical depending on access",
    updateCadence: "TBD; public access has limits",
    likelyFields: ["date", "country", "airport_or_route_group", "arrival_count", "departure_count", "movement_index"],
    fileFormats: ["API", "CSV exports TBD"],
    accessType: "public_api",
    licenseNotes: "Confirm API terms, rate limits, and permitted use.",
    provenanceNotes: "Use only aggregate route or airport indexes in this dashboard.",
    dataQualityNotes: "ADS-B coverage is uneven; public API is not a complete traffic census.",
    limitations: "Do not expose flight-level traces in the frontend.",
    adapterStatus: "backend_required",
    mvpStatus: "keep",
    countryAvailability: "global_source_unknown_country_filter",
    lastVerifiedDate: verified,
    userAdded: false
  },
  {
    id: "ourairports",
    name: "OurAirports",
    category: "mobility_air_travel",
    description: "Global airport reference dataset for static airport metadata.",
    officialUrl: "https://ourairports.com/data/",
    owner: "OurAirports",
    geographicCoverage: "Global",
    supportedCountries: ["GLOBAL"],
    granularity: "Airport point locations",
    temporalResolution: "Current reference snapshot",
    updateCadence: "Frequent community updates",
    likelyFields: ["airport_id", "name", "iata", "icao", "latitude", "longitude", "country"],
    fileFormats: ["CSV"],
    accessType: "downloadable_file",
    licenseNotes: "Public dataset; verify current license page before production.",
    provenanceNotes: "Useful for airport reference, not disease or mobility levels.",
    dataQualityNotes: "Community-maintained; may need validation against official registries.",
    limitations: "No passenger volume or live movement data.",
    adapterStatus: "ready",
    mvpStatus: "keep",
    countryAvailability: "global_source_unknown_country_filter",
    lastVerifiedDate: verified,
    userAdded: false
  },
  {
    id: "imf-portwatch",
    name: "IMF PortWatch / UN AIS-derived port activity",
    category: "ports_maritime_cargo",
    description: "Public platform for monitoring maritime trade disruptions using satellite AIS-derived indicators.",
    officialUrl: "https://portwatch.imf.org/",
    owner: "IMF and University of Oxford",
    geographicCoverage: "Global major ports and maritime chokepoints",
    supportedCountries: ["GLOBAL"],
    granularity: "Daily port and chokepoint indicators",
    temporalResolution: "Daily",
    updateCadence: "Frequent ArcGIS service refresh; subject to revisions",
    likelyFields: ["date", "portid", "portname", "country", "ISO3", "portcalls", "imports", "exports", "capacity"],
    fileFormats: ["ArcGIS REST JSON", "GeoJSON", "CSV", "KML", "Excel"],
    accessType: "public_api",
    licenseNotes: "Confirm PortWatch terms; IMF labels some nowcasts as experimental.",
    provenanceNotes: "Uses satellite AIS and modelled trade/capacity estimates.",
    dataQualityNotes: "AIS-derived; estimates can be revised.",
    limitations: "Not customs trade and not raw AIS; methodology changes possible.",
    adapterStatus: "partial",
    mvpStatus: "keep",
    countryAvailability: "global_source_unknown_country_filter",
    lastVerifiedDate: verified,
    userAdded: false
  },
  {
    id: "nga-world-port-index",
    name: "NGA World Port Index (Pub. 150)",
    category: "ports_maritime_cargo",
    description: "Global port and terminal reference dataset with location, facilities, services, and physical characteristics.",
    officialUrl: "https://msi.nga.mil/Publications/WPI",
    owner: "National Geospatial-Intelligence Agency",
    geographicCoverage: "Global",
    supportedCountries: ["GLOBAL"],
    granularity: "Port / terminal point",
    temporalResolution: "Current reference snapshot",
    updateCadence: "Monthly or periodic WPI refresh; verify file timestamp on ingest",
    likelyFields: ["index_number", "port_name", "country", "latitude", "longitude", "harbor_size", "depths", "pilotage", "tugs", "cranes"],
    fileFormats: ["CSV", "GeoPackage", "GeoJSON", "Shapefile", "FileGDB", "PDF"],
    accessType: "downloadable_file",
    licenseNotes: "U.S. government source; confirm current public-domain and attribution notes.",
    provenanceNotes: "Strong global seed for port attributes and location joins.",
    dataQualityNotes: "Some coded fields require WPI dictionary interpretation.",
    limitations: "Facility attributes may lag local changes; not a port activity feed.",
    adapterStatus: "partial",
    mvpStatus: "add",
    countryAvailability: "global_source_unknown_country_filter",
    lastVerifiedDate: verified,
    userAdded: false
  },
  {
    id: "usace-navigation-facilities",
    name: "USACE WCSC Navigation Facilities",
    category: "ports_maritime_cargo",
    description: "U.S. inventory of docks, terminals, anchorage areas, and navigation facilities.",
    officialUrl: "https://www.iwr.usace.army.mil/About/Technical-Centers/WCSC-Waterborne-Commerce-Statistics-Center/WCSC-Navigation-Facilities/",
    owner: "USACE Waterborne Commerce Statistics Center",
    geographicCoverage: "United States, Great Lakes, inland waterways, Alaska, Hawaii, Puerto Rico, U.S. territories",
    supportedCountries: ["USA"],
    granularity: "Dock, terminal, anchorage, fleeting area, navigation facility",
    temporalResolution: "Current facility inventory",
    updateCadence: "Quarterly for navigation points of interest; other facilities periodic",
    likelyFields: ["navigation_unit_id", "facility_name", "facility_type", "unlocode", "latitude", "longitude", "waterway", "owner", "operator"],
    fileFormats: ["Feature service", "Shapefile", "GeoJSON", "CSV", "Excel", "FileGDB"],
    accessType: "downloadable_file",
    licenseNotes: "U.S. government public source; verify metadata use constraints.",
    provenanceNotes: "Authoritative U.S. navigation infrastructure inventory.",
    dataQualityNotes: "Operational attributes can be stale and require facility QA.",
    limitations: "U.S.-centric and not a real-time activity source.",
    adapterStatus: "placeholder",
    mvpStatus: "add",
    countryAvailability: "available",
    lastVerifiedDate: verified,
    userAdded: false
  },
  {
    id: "noaa-marine-cadastre-ais",
    name: "NOAA / BOEM Marine Cadastre AIS Vessel Traffic",
    category: "ports_maritime_cargo",
    description: "Official public U.S. AIS vessel traffic products for coastal and ocean planning.",
    officialUrl: "https://coast.noaa.gov/digitalcoast/data/vesseltraffic.html",
    owner: "NOAA Office for Coastal Management, BOEM, U.S. Coast Guard",
    geographicCoverage: "U.S. coastal/offshore waters and territories",
    supportedCountries: ["USA"],
    granularity: "AIS point records, vessel tracks, or gridded transit counts depending on product",
    temporalResolution: "Timestamped points, monthly files, and annual derived products",
    updateCadence: "Annual public releases; AccessAIS recent-year data added quarterly",
    likelyFields: ["date", "region_or_grid", "vessel_type", "transit_count", "aggregate_hours", "source_release"],
    fileFormats: ["CSV", "GeoPackage", "GeoTIFF", "Esri services"],
    accessType: "downloadable_file",
    licenseNotes: "Official public product; use constraints say not for navigation.",
    provenanceNotes: "Derived from U.S. Coast Guard AIS collection and NOAA/BOEM processing.",
    dataQualityNotes: "AIS reception bias and processing filters must be documented.",
    limitations: "Do not expose vessel-level traces; aggregate before dashboard display.",
    adapterStatus: "backend_required",
    mvpStatus: "add",
    countryAvailability: "available",
    lastVerifiedDate: verified,
    userAdded: false
  },
  {
    id: "marad-ntad-principal-ports",
    name: "MARAD / BTS / USACE NTAD Principal Ports",
    category: "ports_maritime_cargo",
    description: "Principal U.S. ports geospatial and tonnage reference distributed through federal transportation data resources.",
    officialUrl: "https://www.maritime.dot.gov/data-reports/ports/list",
    owner: "MARAD, BTS NTAD, USACE WCSC",
    geographicCoverage: "United States",
    supportedCountries: ["USA"],
    granularity: "Top principal ports and port statistical areas",
    temporalResolution: "Calendar-year tonnage snapshot",
    updateCadence: "Periodic / annual",
    likelyFields: ["port_code", "port_name", "type", "latitude", "longitude", "total_tons", "imports", "exports"],
    fileFormats: ["ArcGIS FeatureServer", "Shapefile", "FileGDB", "spreadsheet", "ZIP"],
    accessType: "downloadable_file",
    licenseNotes: "U.S. government public resources; verify NTAD metadata.",
    provenanceNotes: "Useful for U.S. port reference and aggregate commerce context.",
    dataQualityNotes: "Top-port definitions can change by year.",
    limitations: "Not all facilities; port limits are statistical and not legal boundaries.",
    adapterStatus: "placeholder",
    mvpStatus: "add",
    countryAvailability: "available",
    lastVerifiedDate: verified,
    userAdded: false
  },
  {
    id: "unece-unlocode",
    name: "UNECE UN/LOCODE",
    category: "ports_maritime_cargo",
    description: "UN-maintained location code system for trade and transport locations.",
    officialUrl: "https://unece.org/trade/uncefact/unlocode",
    owner: "UNECE / UN/CEFACT",
    geographicCoverage: "Global",
    supportedCountries: ["GLOBAL"],
    granularity: "Trade and transport location code",
    temporalResolution: "Release snapshot",
    updateCadence: "Twice yearly",
    likelyFields: ["country", "locode", "location_name", "subdivision", "function", "status", "date", "iata", "coordinates"],
    fileFormats: ["CSV", "TXT", "HTML", "MS Access", "ZIP"],
    accessType: "downloadable_file",
    licenseNotes: "Verify UNECE terms and attribution.",
    provenanceNotes: "Useful for joining port, airport, rail, and logistics datasets.",
    dataQualityNotes: "Coordinates and function flags can be coarse.",
    limitations: "Reference code list, not a traffic or surveillance source.",
    adapterStatus: "ready",
    mvpStatus: "add",
    countryAvailability: "global_source_unknown_country_filter",
    lastVerifiedDate: verified,
    userAdded: false
  },
  {
    id: "teammate-wastewater",
    name: "Future teammate-provided wastewater dataset",
    category: "wastewater",
    description: "Placeholder for project-specific wastewater pipeline delivered by teammates.",
    officialUrl: "",
    owner: "Future teammate pipeline",
    geographicCoverage: "TBD",
    supportedCountries: [],
    granularity: "TBD",
    temporalResolution: "TBD",
    updateCadence: "TBD",
    likelyFields: ["date", "geography", "target", "normalized_signal", "trend", "quality_flags"],
    fileFormats: ["CSV", "JSON", "API TBD"],
    accessType: "backend_required",
    licenseNotes: "TBD",
    provenanceNotes: "Schema and QA rules must be documented before display.",
    dataQualityNotes: "TBD",
    limitations: "No data connected in the MVP.",
    adapterStatus: "backend_required",
    mvpStatus: "later",
    countryAvailability: "unknown",
    lastVerifiedDate: verified,
    userAdded: false
  },
  {
    id: "teammate-mobility",
    name: "Future teammate-provided mobility dataset",
    category: "mobility_air_travel",
    description: "Placeholder for aggregate mobility pipeline delivered by teammates.",
    officialUrl: "",
    owner: "Future teammate pipeline",
    geographicCoverage: "TBD",
    supportedCountries: [],
    granularity: "TBD",
    temporalResolution: "TBD",
    updateCadence: "TBD",
    likelyFields: ["date", "geography", "inbound_index", "outbound_index", "local_movement_index"],
    fileFormats: ["CSV", "JSON", "API TBD"],
    accessType: "backend_required",
    licenseNotes: "TBD",
    provenanceNotes: "Must remain aggregate and privacy-preserving.",
    dataQualityNotes: "TBD",
    limitations: "No individual-level traces or device data should be accepted.",
    adapterStatus: "backend_required",
    mvpStatus: "later",
    countryAvailability: "unknown",
    lastVerifiedDate: verified,
    userAdded: false
  },
  {
    id: "teammate-ferry-cargo",
    name: "Future teammate-provided ferry/cargo dataset",
    category: "ports_maritime_cargo",
    description: "Placeholder for aggregate ferry, cargo, or port-movement pipeline.",
    officialUrl: "",
    owner: "Future teammate pipeline",
    geographicCoverage: "TBD",
    supportedCountries: [],
    granularity: "Route, port, or region aggregates",
    temporalResolution: "TBD",
    updateCadence: "TBD",
    likelyFields: ["date", "route_group", "origin_region", "destination_region", "volume_index"],
    fileFormats: ["CSV", "JSON", "API TBD"],
    accessType: "backend_required",
    licenseNotes: "TBD",
    provenanceNotes: "Should be aggregated before frontend display.",
    dataQualityNotes: "TBD",
    limitations: "Avoid operationally sensitive or vessel-level detail.",
    adapterStatus: "backend_required",
    mvpStatus: "later",
    countryAvailability: "unknown",
    lastVerifiedDate: verified,
    userAdded: false
  },
  {
    id: "teammate-pop-density",
    name: "Future teammate-provided population-density dataset",
    category: "population_demographics",
    description: "Placeholder for population and demographic context data.",
    officialUrl: "",
    owner: "Future teammate pipeline",
    geographicCoverage: "TBD",
    supportedCountries: [],
    granularity: "Grid, admin unit, or country",
    temporalResolution: "TBD",
    updateCadence: "TBD",
    likelyFields: ["geography_id", "population", "density", "urbanicity", "update_year"],
    fileFormats: ["CSV", "GeoJSON", "API TBD"],
    accessType: "backend_required",
    licenseNotes: "TBD",
    provenanceNotes: "Context only; no individual-level data.",
    dataQualityNotes: "Must normalize geography definitions before comparison.",
    limitations: "No data connected in the MVP.",
    adapterStatus: "backend_required",
    mvpStatus: "later",
    countryAvailability: "unknown",
    lastVerifiedDate: verified,
    userAdded: false
  },
  {
    id: "future-news-backend",
    name: "Future country news / event surveillance backend",
    category: "news_event_surveillance",
    description: "Placeholder endpoint for curated country-level public-health news and event surveillance summaries.",
    officialUrl: "/api/countries/:iso3/news/latest",
    owner: "Future backend service",
    geographicCoverage: "TBD",
    supportedCountries: [],
    granularity: "Country-level news item or summary",
    temporalResolution: "Publication date",
    updateCadence: "TBD",
    likelyFields: ["headline", "date", "source", "country", "related_signal", "confidence_status", "url"],
    fileFormats: ["JSON API"],
    accessType: "backend_required",
    licenseNotes: "TBD by backend source agreements.",
    provenanceNotes: "Frontend must not scrape websites directly.",
    dataQualityNotes: "Backend should classify source confidence and deduplicate items.",
    limitations: "No news feed connected yet.",
    adapterStatus: "backend_required",
    mvpStatus: "later",
    countryAvailability: "unknown",
    lastVerifiedDate: verified,
    userAdded: false
  }
];

function legacyMvpStatus(source: DataSourceMetadata): LegacySourceMvpStatus {
  if (source.mvpStatus === "later" || source.mvpStatus === "user_added") {
    return "later";
  }

  if (source.id === "ourairports") {
    return "include now";
  }

  return "placeholder";
}

function countryStatus(source: DataSourceMetadata): SourceCountryCoverageStatus {
  if (source.countryAvailability === "available") {
    return "available";
  }

  if (source.countryAvailability === "global_source_unknown_country_filter") {
    return "candidate";
  }

  if (source.countryAvailability === "unavailable") {
    return "planned";
  }

  return "unknown";
}

function coverageGranularity(source: DataSourceMetadata): SourceCountryGranularity {
  const text = `${source.category} ${source.granularity}`.toLowerCase();

  if (text.includes("grid")) return "grid";
  if (text.includes("route")) return "route-aggregate";
  if (text.includes("airport") || text.includes("port") || text.includes("point") || text.includes("facility")) return "point";
  if (text.includes("site") || text.includes("sewershed")) return "site";
  if (text.includes("state") || text.includes("jurisdiction")) return "admin1";
  if (text.includes("global")) return "global";
  return "country";
}

function coverageForSource(source: DataSourceMetadata): SourceCountryCoverage[] {
  if (source.countryCoverage?.length) {
    return source.countryCoverage;
  }

  const countries = source.supportedCountries.length > 0 ? source.supportedCountries : ["TBD"];
  return countries.map((iso3) => ({
    iso3,
    countryName: iso3 === "GLOBAL" ? "Global" : iso3 === "TBD" ? "To be determined" : iso3,
    status: countryStatus(source),
    granularity: iso3 === "GLOBAL" ? "global" : coverageGranularity(source),
    notes: source.geographicCoverage
  }));
}

function signalCoverageForSource(source: DataSourceMetadata): string {
  switch (source.category) {
    case "wastewater":
      return "Pathogen targets and wastewater activity metrics where reported";
    case "forecasts_nowcasts":
      return "Forecast and nowcast targets where published";
    case "mobility_air_travel":
      return "Mobility signal, not pathogen-specific";
    case "ports_maritime_cargo":
      return "Mobility and commerce signal, not pathogen-specific";
    case "population_demographics":
      return "Context layer only";
    case "news_event_surveillance":
      return "Country-level event context only";
    case "user_added":
      return "User-supplied aggregate source metadata";
    case "pathogen_surveillance":
    default:
      return "Country-level pathogen surveillance indicators where reported";
  }
}

function privacyClassificationForSource(source: DataSourceMetadata): CatalogSourceMetadata["privacyClassification"] {
  const text = `${source.description} ${source.limitations} ${source.provenanceNotes}`.toLowerCase();
  if (text.includes("flight-level") || text.includes("vessel-level") || text.includes("ais") || text.includes("trace")) {
    return "sensitive aggregate";
  }

  if (source.accessType === "backend_required" || source.accessType === "user_upload") {
    return "aggregate restricted";
  }

  return "aggregate public";
}

export const sourceCatalog: CatalogSourceMetadata[] = sourceCatalogRecords.map((source) => ({
  ...source,
  sourceName: source.sourceName ?? source.name,
  dataType: source.dataType ?? sourceCategoryLabels[source.category],
  pathogenOrSignalCoverage: source.pathogenOrSignalCoverage ?? signalCoverageForSource(source),
  geographyGranularity: source.geographyGranularity ?? source.granularity,
  relevance: source.relevance ?? source.provenanceNotes ?? source.description,
  mvpStatus: legacyMvpStatus(source),
  countryCoverage: coverageForSource(source),
  validationStatus: source.validationStatus ?? (source.adapterStatus === "ready" ? "public metadata reviewed" : "adapter candidate"),
  privacyClassification: source.privacyClassification ?? privacyClassificationForSource(source),
  aggregateOnly: source.aggregateOnly ?? true
}));
