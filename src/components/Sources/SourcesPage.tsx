import { useEffect, useMemo, useState } from "react";
import type { AddSourceInput, DataSourceMetadata, SourceValidationResult } from "../../types/source";
import type { SelectedCountry } from "../../types/dashboard";
import { getSourcesForCountry } from "../../data/adapters/sourceRegistryAdapter";
import { orderedSourceCategories, sourceCategoryLabels } from "../../data/sources/sourceCategories";
import { Panel } from "../ui/Panel";
import { EmptyState } from "../ui/EmptyState";
import { AddSourceModal } from "./AddSourceModal";
import { SourceCard } from "./SourceCard";
import { SourceCoverageMatrix } from "./SourceCoverageMatrix";

interface SourcesPageProps {
  selectedCountry: SelectedCountry | null;
  sources: DataSourceMetadata[];
  onAddSource: (input: AddSourceInput) => SourceValidationResult | { source?: DataSourceMetadata; validation: SourceValidationResult };
  onSourcesChange?: (sources: DataSourceMetadata[]) => void;
}

function validationFromAddResult(result: SourceValidationResult | { source?: DataSourceMetadata; validation: SourceValidationResult }) {
  return "validation" in result ? result.validation : result;
}

function sourceFromAddResult(result: SourceValidationResult | { source?: DataSourceMetadata; validation: SourceValidationResult }) {
  return "validation" in result ? result.source : undefined;
}

export function SourcesPage({ selectedCountry, sources, onAddSource, onSourcesChange }: SourcesPageProps) {
  const [modalOpen, setModalOpen] = useState(false);
  const [localSources, setLocalSources] = useState(sources);
  const countrySources = useMemo(() => getSourcesForCountry(localSources, selectedCountry?.iso3 ?? null), [localSources, selectedCountry?.iso3]);

  useEffect(() => {
    setLocalSources(sources);
  }, [sources]);

  const handleAddSource = (input: AddSourceInput): SourceValidationResult => {
    const result = onAddSource(input);
    const validation = validationFromAddResult(result);
    const addedSource = sourceFromAddResult(result);

    if (validation.valid && addedSource) {
      const nextSources = [...localSources, addedSource];
      setLocalSources(nextSources);
      onSourcesChange?.(nextSources);
    }

    return validation;
  };

  if (!selectedCountry) {
    return (
      <Panel eyebrow="Sources" title="Select a country first">
        <EmptyState title="Select a country on the world map first." body="Country selection happens on the map so source availability can be filtered by ISO code." />
      </Panel>
    );
  }

  return (
    <div className="space-y-5">
      <div className="flex flex-col gap-4 rounded-2xl border border-white/10 bg-black p-5 text-white lg:flex-row lg:items-center lg:justify-between">
        <div>
          <p className="text-xs font-semibold uppercase text-red-300">Sources</p>
          <h1 className="mt-1 text-3xl font-semibold">Available Data Sources for {selectedCountry.name}</h1>
          <p className="mt-2 max-w-3xl text-sm leading-6 text-neutral-400">
            Registry entries describe possible aggregate data sources. They do not imply live ingestion or validation.
          </p>
        </div>
        <button className="rounded-md bg-red-700 px-4 py-2 text-sm font-semibold text-white hover:bg-red-800" type="button" onClick={() => setModalOpen(true)}>
          Add source
        </button>
      </div>

      <SourceCoverageMatrix sources={countrySources} focusCountry={selectedCountry} />

      {countrySources.length === 0 ? (
        <Panel>
          <EmptyState title="No verified sources added yet" body="Add a local source or return later when a backend adapter is connected for this country." />
        </Panel>
      ) : (
        <div className="space-y-6">
          {orderedSourceCategories.map((category) => {
            const grouped = countrySources.filter((source) => source.category === category);
            if (grouped.length === 0) return null;
            return (
              <section key={category} className="space-y-3">
                <h2 className="text-sm font-semibold uppercase text-neutral-300">{sourceCategoryLabels[category]}</h2>
                <div className="grid gap-4 xl:grid-cols-2">
                  {grouped.map((source) => (
                    <SourceCard key={source.id} source={source} />
                  ))}
                </div>
              </section>
            );
          })}
        </div>
      )}

      {modalOpen && (
        <AddSourceModal defaultCountryIso3={selectedCountry.iso3} onClose={() => setModalOpen(false)} onSubmit={handleAddSource} />
      )}
    </div>
  );
}
