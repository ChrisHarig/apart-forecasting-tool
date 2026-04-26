import { useState } from "react";
import { ArrowLeft, ExternalLink, Globe2, LineChart, Loader2 } from "lucide-react";
import { useDashboard } from "../../state/DashboardContext";
import { useDatasetSlice } from "../../data/hf/hooks";
import { SourceTimelineChart } from "../Graph/SourceTimelineChart";
import { DataTable } from "../Graph/DataTable";
import { DatasetMap } from "./DatasetMap";

type ExplorerTab = "graph" | "map";

export function ExplorerPage() {
  const { explorerSourceId, catalog, setView } = useDashboard();
  const source = catalog.data?.find((s) => s.id === explorerSourceId) ?? null;
  const slice = useDatasetSlice(source?.id ?? null);
  const [tab, setTab] = useState<ExplorerTab>("graph");

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

      <div className="flex items-center gap-1 rounded-md border border-white/10 bg-white/[0.02] p-1 w-fit">
        <TabButton active={tab === "graph"} onClick={() => setTab("graph")} icon={LineChart} label="Graph" />
        <TabButton active={tab === "map"} onClick={() => setTab("map")} icon={Globe2} label="Map" />
      </div>

      {slice.status === "loading" && (
        <div className="flex items-center gap-3 rounded-xl border border-white/10 bg-white/[0.03] px-5 py-6">
          <Loader2 className="h-6 w-6 shrink-0 animate-spin text-red-400" aria-hidden="true" />
          <div>
            <p className="text-base font-semibold text-white">Fetching data from Huggingface…</p>
            <p className="text-xs text-neutral-400">Pulling rows for {source.pretty_name}.</p>
          </div>
        </div>
      )}
      {slice.status === "error" && <p className="text-sm text-red-200">Failed to load: {slice.error}</p>}
      {slice.status === "ready" && slice.data && (
        <>
          {tab === "graph" ? (
            <SourceTimelineChart source={source} rows={slice.data.rows} />
          ) : (
            <DatasetMap source={source} rows={slice.data.rows} />
          )}
          <DataTable rows={slice.data.rows} />
          {slice.data.truncated && (
            <p className="text-[11px] text-neutral-500">
              Showing the first {slice.data.rows.length.toLocaleString()} rows of{" "}
              {slice.data.numRowsTotal.toLocaleString()}.
            </p>
          )}
        </>
      )}
    </div>
  );
}

interface TabButtonProps {
  active: boolean;
  onClick: () => void;
  icon: React.ComponentType<React.SVGProps<SVGSVGElement>>;
  label: string;
}

function TabButton({ active, onClick, icon: Icon, label }: TabButtonProps) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={`flex items-center gap-1.5 rounded px-3 py-1.5 text-xs font-semibold transition ${
        active
          ? "bg-red-700/40 text-red-100"
          : "text-neutral-300 hover:bg-white/[0.05] hover:text-white"
      }`}
      aria-pressed={active}
    >
      <Icon className="h-3.5 w-3.5" />
      <span>{label}</span>
    </button>
  );
}
