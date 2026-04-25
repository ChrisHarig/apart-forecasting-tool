"""Infrastructure and mobility source connector placeholders."""

from __future__ import annotations

from .base import (
    PlaceholderGeospatialConnector,
    PlaceholderSourceMetadataConnector,
    PlaceholderTimeSeriesConnector,
    source_description,
)

VERIFIED = "2026-04-25"


class OpenSkyConnector(PlaceholderTimeSeriesConnector):
    metadata = source_description(
        source_id="opensky",
        name="OpenSky Network",
        category="mobility_air_travel",
        owner="OpenSky Network",
        official_url="https://opensky-network.org/",
        description="Aircraft movement data source candidate for aggregate airport movement context.",
        geographic_coverage="Global ADS-B coverage with regional gaps",
        supported_countries=("GLOBAL",),
        granularity="Flight or airport-derived aggregates after privacy-preserving processing",
        temporal_resolution="Near-real-time / historical depending on access",
        update_cadence="TBD; public access has limits",
        likely_fields=("date", "country", "airport_or_route_group", "arrival_count", "departure_count", "movement_index"),
        file_formats=("API", "CSV exports TBD"),
        access_type="public_api",
        license_notes="Confirm API terms, rate limits, and permitted use.",
        provenance_notes="Use only aggregate route or airport indexes in this dashboard.",
        data_quality_notes="ADS-B coverage is uneven; public API is not a complete traffic census.",
        limitations="Do not expose flight-level traces in the frontend.",
        adapter_status="backend_required",
        country_availability="global_source_unknown_country_filter",
        last_verified_date=VERIFIED,
        privacy_classification="sensitive aggregate",
        warnings=("Raw aircraft traces are out of scope; only aggregate airport or route indicators are allowed.",),
    )


class OurAirportsConnector(PlaceholderGeospatialConnector):
    metadata = source_description(
        source_id="ourairports",
        name="OurAirports",
        category="mobility_air_travel",
        owner="OurAirports",
        official_url="https://ourairports.com/data/",
        description="Global airport reference dataset for static airport metadata.",
        geographic_coverage="Global",
        supported_countries=("GLOBAL",),
        granularity="Airport point locations",
        temporal_resolution="Current reference snapshot",
        update_cadence="Frequent community updates",
        likely_fields=("airport_id", "name", "iata", "icao", "latitude", "longitude", "country"),
        file_formats=("CSV",),
        access_type="downloadable_file",
        license_notes="Public dataset; verify current license page before production.",
        provenance_notes="Useful for airport reference, not disease or mobility levels.",
        data_quality_notes="Community-maintained; may need validation against official registries.",
        limitations="No passenger volume or live movement data.",
        adapter_status="placeholder",
        country_availability="global_source_unknown_country_filter",
        last_verified_date=VERIFIED,
    )


class IMFPortWatchConnector(PlaceholderTimeSeriesConnector):
    metadata = source_description(
        source_id="imf-portwatch",
        name="IMF PortWatch / UN AIS-derived port activity",
        category="ports_maritime_cargo",
        owner="IMF and University of Oxford",
        official_url="https://portwatch.imf.org/",
        description="Public platform for monitoring maritime trade disruptions using satellite AIS-derived indicators.",
        geographic_coverage="Global major ports and maritime chokepoints",
        supported_countries=("GLOBAL",),
        granularity="Daily port and chokepoint indicators",
        temporal_resolution="Daily",
        update_cadence="Frequent ArcGIS service refresh; subject to revisions",
        likely_fields=("date", "portid", "portname", "country", "ISO3", "portcalls", "imports", "exports", "capacity"),
        file_formats=("ArcGIS REST JSON", "GeoJSON", "CSV", "KML", "Excel"),
        access_type="public_api",
        license_notes="Confirm PortWatch terms; IMF labels some nowcasts as experimental.",
        provenance_notes="Uses satellite AIS and modelled trade/capacity estimates.",
        data_quality_notes="AIS-derived; estimates can be revised.",
        limitations="Not customs trade and not raw AIS; methodology changes possible.",
        adapter_status="partial",
        country_availability="global_source_unknown_country_filter",
        last_verified_date=VERIFIED,
        privacy_classification="aggregate public",
        model_readiness={
            "status": "requires_review",
            "allowed_use": ["source discovery", "historical aggregate context", "data quality review"],
            "blocked_use": ["production prediction", "operational routing", "raw vessel tracking"],
            "requirements_before_modeling": [
                "methodology review",
                "revision policy review",
                "country and port coverage checks",
                "clear separation from public-health risk scoring",
            ],
        },
    )


class NGAWorldPortIndexConnector(PlaceholderGeospatialConnector):
    metadata = source_description(
        source_id="nga-world-port-index",
        name="NGA World Port Index (Pub. 150)",
        category="ports_maritime_cargo",
        owner="National Geospatial-Intelligence Agency",
        official_url="https://msi.nga.mil/Publications/WPI",
        description="Global port and terminal reference dataset with location, facilities, services, and physical characteristics.",
        geographic_coverage="Global",
        supported_countries=("GLOBAL",),
        granularity="Port / terminal point",
        temporal_resolution="Current reference snapshot",
        update_cadence="Monthly or periodic WPI refresh; verify file timestamp on ingest",
        likely_fields=("index_number", "port_name", "country", "latitude", "longitude", "harbor_size", "depths", "pilotage"),
        file_formats=("CSV", "GeoPackage", "GeoJSON", "Shapefile", "FileGDB", "PDF"),
        access_type="downloadable_file",
        license_notes="U.S. government source; confirm current public-domain and attribution notes.",
        provenance_notes="Strong global seed for port attributes and location joins.",
        data_quality_notes="Some coded fields require WPI dictionary interpretation.",
        limitations="Facility attributes may lag local changes; not a port activity feed.",
        adapter_status="partial",
        country_availability="global_source_unknown_country_filter",
        last_verified_date=VERIFIED,
    )


class USACENavigationConnector(PlaceholderGeospatialConnector):
    metadata = source_description(
        source_id="usace-navigation-facilities",
        name="USACE WCSC Navigation Facilities",
        category="ports_maritime_cargo",
        owner="USACE Waterborne Commerce Statistics Center",
        official_url="https://www.iwr.usace.army.mil/About/Technical-Centers/WCSC-Waterborne-Commerce-Statistics-Center/WCSC-Navigation-Facilities/",
        description="U.S. inventory of docks, terminals, anchorage areas, and navigation facilities.",
        geographic_coverage="United States, Great Lakes, inland waterways, Alaska, Hawaii, Puerto Rico, U.S. territories",
        supported_countries=("USA",),
        granularity="Dock, terminal, anchorage, fleeting area, navigation facility",
        temporal_resolution="Current facility inventory",
        update_cadence="Quarterly for navigation points of interest; other facilities periodic",
        likely_fields=("navigation_unit_id", "facility_name", "facility_type", "unlocode", "latitude", "longitude", "waterway"),
        file_formats=("Feature service", "Shapefile", "GeoJSON", "CSV", "Excel", "FileGDB"),
        access_type="downloadable_file",
        license_notes="U.S. government public source; verify metadata use constraints.",
        provenance_notes="Authoritative U.S. navigation infrastructure inventory.",
        data_quality_notes="Operational attributes can be stale and require facility QA.",
        limitations="U.S.-centric and not a real-time activity source.",
        adapter_status="placeholder",
        country_availability="available",
        last_verified_date=VERIFIED,
    )


class NOAAAISConnector(PlaceholderTimeSeriesConnector):
    metadata = source_description(
        source_id="noaa-marine-cadastre-ais",
        name="NOAA / BOEM Marine Cadastre AIS Vessel Traffic",
        category="ports_maritime_cargo",
        owner="NOAA Office for Coastal Management, BOEM, U.S. Coast Guard",
        official_url="https://coast.noaa.gov/digitalcoast/data/vesseltraffic.html",
        description="Official public U.S. AIS vessel traffic products for coastal and ocean planning.",
        geographic_coverage="U.S. coastal/offshore waters and territories",
        supported_countries=("USA",),
        granularity="AIS point records, vessel tracks, or gridded transit counts depending on product",
        temporal_resolution="Timestamped points, monthly files, and annual derived products",
        update_cadence="Annual public releases; AccessAIS recent-year data added quarterly",
        likely_fields=("date", "region_or_grid", "vessel_type", "transit_count", "aggregate_hours", "source_release"),
        file_formats=("CSV", "GeoPackage", "GeoTIFF", "Esri services"),
        access_type="downloadable_file",
        license_notes="Official public product; use constraints say not for navigation.",
        provenance_notes="Derived from U.S. Coast Guard AIS collection and NOAA/BOEM processing.",
        data_quality_notes="AIS reception bias and processing filters must be documented.",
        limitations="Do not expose vessel-level traces; aggregate before dashboard display.",
        adapter_status="backend_required",
        country_availability="available",
        last_verified_date=VERIFIED,
        privacy_classification="sensitive aggregate",
        warnings=("Raw AIS rows are out of scope; only gridded or regional aggregate counts are allowed.",),
    )


class MARADPortsConnector(PlaceholderGeospatialConnector):
    metadata = source_description(
        source_id="marad-ntad-principal-ports",
        name="MARAD / BTS / USACE NTAD Principal Ports",
        category="ports_maritime_cargo",
        owner="MARAD, BTS NTAD, USACE WCSC",
        official_url="https://www.maritime.dot.gov/data-reports/ports/list",
        description="Principal U.S. ports geospatial and tonnage reference distributed through federal transportation data resources.",
        geographic_coverage="United States",
        supported_countries=("USA",),
        granularity="Top principal ports and port statistical areas",
        temporal_resolution="Calendar-year tonnage snapshot",
        update_cadence="Periodic / annual",
        likely_fields=("port_code", "port_name", "type", "latitude", "longitude", "total_tons", "imports", "exports"),
        file_formats=("ArcGIS FeatureServer", "Shapefile", "FileGDB", "spreadsheet", "ZIP"),
        access_type="downloadable_file",
        license_notes="U.S. government public resources; verify NTAD metadata.",
        provenance_notes="Useful for U.S. port reference and aggregate commerce context.",
        data_quality_notes="Top-port definitions can change by year.",
        limitations="Not all facilities; port limits are statistical and not legal boundaries.",
        adapter_status="placeholder",
        country_availability="available",
        last_verified_date=VERIFIED,
    )


class UserUploadConnector(PlaceholderSourceMetadataConnector):
    metadata = source_description(
        source_id="user-upload",
        name="User-uploaded aggregate source",
        category="user_added",
        owner="Workspace user/team",
        official_url="",
        description="Placeholder for authenticated server-side storage of user-uploaded aggregate CSV/JSON datasets.",
        geographic_coverage="User-declared and validation-dependent",
        supported_countries=(),
        granularity="Country, admin, site, or other aggregate geography declared by the upload",
        temporal_resolution="Declared by upload",
        update_cadence="User-managed",
        likely_fields=("date", "country_iso3", "metric", "value", "unit", "provenance", "quality_flag"),
        file_formats=("CSV", "JSON"),
        access_type="user_upload",
        license_notes="Uploader must provide rights and attribution for each dataset.",
        provenance_notes="Uploads require explicit provenance before display.",
        data_quality_notes="Schema, date bounds, duplicates, and missingness must be validated per upload.",
        limitations="No upload persistence is implemented in this scaffold.",
        adapter_status="placeholder",
        country_availability="unknown",
        last_verified_date=VERIFIED,
        privacy_classification="aggregate restricted",
        warnings=("User-added sources are not validated until reviewed.",),
    )
