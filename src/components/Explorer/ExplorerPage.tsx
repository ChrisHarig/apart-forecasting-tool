import { ArrowLeft, ExternalLink } from "lucide-react";
import { useDashboard } from "../../state/DashboardContext";
import { useDatasetSlice } from "../../data/hf/hooks";
import { SourceTimelineChart } from "../Graph/SourceTimelineChart";
import { DataTable } from "../Graph/DataTable";

export function ExplorerPage() {
  const { explorerSourceId, catalog, setView } = useDashboard();
  const source = catalog.data?.find((s) => s.id === explorerSourceId) ?? null;
  const slice = useDatasetSlice(source?.id ?? null);

  if (!source) {
    return (
      <div className="rounded-xl border border-white/10 bg-white/[0.03] p-6 text-sm text-neutral-300">
        <p className="font-semibold text-white">No dataset open.</p>
        <p className="mt-1 text-neutral-400">
          Click <em>Open data</em> on a dataset in the{" "}
          <button type="button" onClick={() => setView("feed")} className="text-red-300 underline hover:text-red-200">
            Feed
          </button>{" "}
          to inspect it here.
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-3">
      <header className="rounded-xl border border-white/10 bg-black/60 px-4 py-3">
        <div className="flex flex-wrap items-center gap-3">
          <button
            type="button"
            onClick={() => setView("feed")}
            className="flex items-center gap-1 rounded-md border border-white/10 px-2 py-1 text-xs text-neutral-200 hover:border-red-500 hover:text-red-200"
          >
            <ArrowLeft className="h-3 w-3" /> Feed
          </button>
          <h1 className="text-base font-semibold text-white">{source.pretty_name}</h1>
          <span className="font-mono text-[10px] text-neutral-500">{source.id}</span>
          {source.source_url && (
            <a
              href={source.source_url}
              target="_blank"
              rel="noreferrer"
              className="ml-auto flex items-center gap-1 text-xs text-red-300 hover:text-red-200"
            >
              Source <ExternalLink className="h-3 w-3" />
            </a>
          )}
        </div>
        {source.description && <p className="mt-2 text-xs leading-5 text-neutral-300">{source.description}</p>}
      </header>

      {slice.status === "loading" && <p className="text-sm text-neutral-300">Fetching rows from Huggingface…</p>}
      {slice.status === "error" && <p className="text-sm text-red-200">Failed to load: {slice.error}</p>}
      {slice.status === "ready" && slice.data && (
        <div className="space-y-3">
          <SourceTimelineChart source={source} rows={slice.data.rows} />
          <DataTable rows={slice.data.rows} />
          {slice.data.truncated && (
            <p className="text-[11px] text-neutral-500">
              Showing the first {slice.data.rows.length.toLocaleString()} rows of{" "}
              {slice.data.numRowsTotal.toLocaleString()}.
            </p>
          )}
        </div>
      )}
    </div>
  );
}
