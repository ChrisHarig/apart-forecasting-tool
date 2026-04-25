import { useMemo } from "react";
import type { DataSourceMetadata, SourceCategory, SourceCountryCoverageStatus } from "../../types/source";
import type { SelectedCountry } from "../../types/dashboard";
import { orderedSourceCategories, sourceCategoryLabels } from "../../data/sources/sourceCategories";
import { StatusPill } from "../ui/StatusPill";

interface SourceCoverageMatrixProps {
  sources: DataSourceMetadata[];
  categories?: SourceCategory[];
  focusCountry?: SelectedCountry | null;
  onCountrySelect?: (iso3: string) => void;
}

interface CoverageCounts {
  total: number;
  available: number;
  candidate: number;
  planned: number;
  unknown: number;
}

interface CountryCoverageRow {
  iso3: string;
  countryName: string;
  countsByCategory: Partial<Record<SourceCategory, CoverageCounts>>;
  total: number;
}

function emptyCounts(): CoverageCounts {
  return {
    total: 0,
    available: 0,
    candidate: 0,
    planned: 0,
    unknown: 0
  };
}

function statusFromSource(source: DataSourceMetadata): SourceCountryCoverageStatus {
  if (source.countryAvailability === "available") return "available";
  if (source.countryAvailability === "unavailable") return "planned";
  if (source.countryAvailability === "global_source_unknown_country_filter") return "candidate";
  return "unknown";
}

function fallbackCountryName(iso3: string): string {
  if (iso3 === "GLOBAL") return "Global";
  if (iso3 === "TBD") return "To be determined";
  return iso3;
}

function increment(counts: CoverageCounts, status: SourceCountryCoverageStatus) {
  counts.total += 1;
  counts[status] += 1;
}

function cellClass(counts: CoverageCounts): string {
  if (counts.available > 0) return "border-white/25 bg-white/[0.08] text-white";
  if (counts.candidate > 0) return "border-red-500/35 bg-red-950/25 text-red-200";
  if (counts.planned > 0) return "border-red-900/45 bg-red-950/15 text-red-300";
  if (counts.unknown > 0) return "border-neutral-400/25 bg-neutral-400/10 text-neutral-300";
  return "border-white/10 bg-white/[0.025] text-neutral-600";
}

function countryFocusedRows(sources: DataSourceMetadata[], categories: SourceCategory[], focusCountry: SelectedCountry): CountryCoverageRow[] {
  const countsByCategory: Partial<Record<SourceCategory, CoverageCounts>> = {};
  let total = 0;

  sources.forEach((source) => {
    if (!categories.includes(source.category)) return;
    const coverageEntry =
      source.countryCoverage?.find((entry) => entry.iso3 === focusCountry.iso3) ??
      source.countryCoverage?.find((entry) => entry.iso3 === "GLOBAL");
    const counts = countsByCategory[source.category] ?? emptyCounts();
    increment(counts, coverageEntry?.status ?? statusFromSource(source));
    countsByCategory[source.category] = counts;
    total += 1;
  });

  return [
    {
      iso3: focusCountry.iso3,
      countryName: focusCountry.name,
      countsByCategory,
      total
    }
  ];
}

export function SourceCoverageMatrix({ sources, categories = orderedSourceCategories, focusCountry, onCountrySelect }: SourceCoverageMatrixProps) {
  const rows = useMemo(() => {
    if (focusCountry) {
      return countryFocusedRows(sources, categories, focusCountry);
    }

    const rowMap = new Map<string, CountryCoverageRow>();

    sources.forEach((source) => {
      const coverage =
        source.countryCoverage && source.countryCoverage.length > 0
          ? source.countryCoverage
          : (source.supportedCountries.length > 0 ? source.supportedCountries : ["TBD"]).map((iso3) => ({
              iso3,
              countryName: fallbackCountryName(iso3),
              status: statusFromSource(source),
              granularity: iso3 === "GLOBAL" ? "global" : "country",
              notes: source.geographicCoverage
            }));

      coverage.forEach((entry) => {
        const row =
          rowMap.get(entry.iso3) ??
          ({
            iso3: entry.iso3,
            countryName: entry.countryName,
            countsByCategory: {},
            total: 0
          } satisfies CountryCoverageRow);
        const counts = row.countsByCategory[source.category] ?? emptyCounts();

        increment(counts, entry.status);
        row.countsByCategory[source.category] = counts;
        row.total += 1;
        rowMap.set(entry.iso3, row);
      });
    });

    return [...rowMap.values()].sort((a, b) => b.total - a.total || a.countryName.localeCompare(b.countryName));
  }, [sources, categories, focusCountry]);

  return (
    <div className="overflow-x-auto rounded-xl border border-white/10 bg-white/[0.04]">
      <table className="min-w-[860px] border-collapse text-left text-xs">
        <thead className="bg-white/[0.06] uppercase text-neutral-300">
          <tr>
            <th className="w-48 px-3 py-3">{focusCountry ? "Selected country" : "Country"}</th>
            {categories.map((category) => (
              <th key={category} className="px-3 py-3">
                {sourceCategoryLabels[category]}
              </th>
            ))}
            <th className="px-3 py-3">Total</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-white/10">
          {rows.map((row) => (
            <tr key={row.iso3} className="hover:bg-white/[0.035]">
              <th className="px-3 py-3 font-semibold text-white">
                {onCountrySelect && !focusCountry ? (
                  <button className="text-left hover:text-red-300" type="button" onClick={() => onCountrySelect(row.iso3)}>
                    <span className="block">{row.countryName}</span>
                    <span className="text-[0.68rem] font-medium uppercase text-neutral-500">{row.iso3}</span>
                  </button>
                ) : (
                  <span className="text-left">
                    <span className="block">{row.countryName}</span>
                    <span className="text-[0.68rem] font-medium uppercase text-neutral-500">{row.iso3}</span>
                  </span>
                )}
              </th>
              {categories.map((category) => {
                const counts = row.countsByCategory[category] ?? emptyCounts();
                return (
                  <td key={category} className="px-3 py-3">
                    <span
                      className={`inline-flex min-w-10 justify-center rounded-md border px-2 py-1 font-semibold ${cellClass(counts)}`}
                      title={`${counts.available} available, ${counts.candidate} candidate, ${counts.planned} planned, ${counts.unknown} unknown`}
                    >
                      {counts.total || "-"}
                    </span>
                  </td>
                );
              })}
              <td className="px-3 py-3">
                <StatusPill tone={row.total > 0 ? "red" : "neutral"}>{row.total}</StatusPill>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      {rows.length === 0 ? <div className="px-4 py-6 text-sm text-neutral-400">No source coverage metadata for this country.</div> : null}
    </div>
  );
}
