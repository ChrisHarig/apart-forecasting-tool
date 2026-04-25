import type { DataSourceMetadata } from "../../types/source";
import { sourceCategoryLabels } from "../../data/sources/sourceCategories";
import { StatusPill } from "../ui/StatusPill";

interface SourceCardProps {
  source: DataSourceMetadata;
  onSelect?: (source: DataSourceMetadata) => void;
  onRemove?: (sourceId: string) => void;
}

export function SourceCard({ source, onSelect, onRemove }: SourceCardProps) {
  return (
    <article className="rounded-xl border border-neutral-200 bg-white p-4 text-black shadow-sm">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <button className="text-left" type="button" onClick={() => onSelect?.(source)}>
          <p className="text-xs font-semibold uppercase text-red-700">{sourceCategoryLabels[source.category]}</p>
          <h3 className="mt-1 text-lg font-semibold">{source.name}</h3>
          <p className="mt-2 text-sm leading-6 text-neutral-700">{source.description}</p>
        </button>
        <div className="flex shrink-0 flex-wrap gap-2">
          <StatusPill tone={source.userAdded ? "redSoft" : source.adapterStatus === "ready" ? "light" : "neutral"}>
            {source.userAdded ? "user added / not validated" : source.adapterStatus.replace("_", " ")}
          </StatusPill>
          <StatusPill tone="neutral">{source.accessType.replace("_", " ")}</StatusPill>
          {source.userAdded && onRemove ? (
            <button
              className="rounded-md border border-neutral-300 px-2 py-1 text-xs font-semibold text-neutral-700 hover:bg-neutral-100"
              type="button"
              onClick={() => onRemove(source.id)}
            >
              Remove
            </button>
          ) : null}
        </div>
      </div>

      <dl className="mt-4 grid gap-3 text-sm md:grid-cols-2">
        <div>
          <dt className="font-semibold text-neutral-950">Publisher</dt>
          <dd className="mt-1 text-neutral-700">{source.owner}</dd>
        </div>
        <div>
          <dt className="font-semibold text-neutral-950">Coverage</dt>
          <dd className="mt-1 text-neutral-700">{source.geographicCoverage}</dd>
        </div>
        <div>
          <dt className="font-semibold text-neutral-950">Granularity</dt>
          <dd className="mt-1 text-neutral-700">{source.granularity}</dd>
        </div>
        <div>
          <dt className="font-semibold text-neutral-950">Cadence</dt>
          <dd className="mt-1 text-neutral-700">{source.updateCadence}</dd>
        </div>
      </dl>

      <div className="mt-4 rounded-lg bg-neutral-100 p-3 text-sm text-neutral-700">
        <p>
          <span className="font-semibold text-neutral-950">Likely fields:</span> {source.likelyFields.join(", ")}
        </p>
        <p className="mt-2">
          <span className="font-semibold text-neutral-950">Limitations:</span> {source.limitations}
        </p>
        {source.warnings?.map((warning) => (
          <p key={warning} className="mt-2 text-red-700">
            {warning}
          </p>
        ))}
      </div>

      {source.officialUrl && (
        <a
          className="mt-4 inline-flex text-sm font-semibold text-red-700 underline-offset-4 hover:underline"
          href={source.officialUrl}
          target="_blank"
          rel="noreferrer"
        >
          Open source reference
        </a>
      )}
    </article>
  );
}
