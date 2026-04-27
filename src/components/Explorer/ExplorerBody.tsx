import type { ComponentType, SVGProps } from "react";
import { ExternalLink, Globe2, LineChart, Loader2, RefreshCw, Table2 } from "lucide-react";
import { useDashboard } from "../../state/DashboardContext";
import { useWorkspace, type ExplorerPane } from "../../state/WorkspaceContext";
import { useDatasetSlice } from "../../data/hf/hooks";
import { SourceTimelineChart } from "../Graph/SourceTimelineChart";
import { DatasetMap } from "./DatasetMap";
import { DataTable } from "../Graph/DataTable";

interface Props {
  pane: ExplorerPane;
}

export function ExplorerBody({ pane }: Props) {
  const { catalog } = useDashboard();
  const { updatePane } = useWorkspace();
  const source = catalog.data?.find((s) => s.id === pane.sourceId) ?? null;
  const slice = useDatasetSlice(pane.sourceId);

  const setTab = (tab: "graph" | "map") =>
    updatePane(pane.id, (p) => (p.type === "explorer" ? { ...p, tab } : p));
  const setShowTable = (showTable: boolean) =>
    updatePane(pane.id, (p) => (p.type === "explorer" ? { ...p, showTable } : p));

  if (!source) {
    return (
      <div className="p-3 text-sm text-neutral-300">
        {catalog.status === "loading"
          ? "Loading catalog…"
          : `Dataset ${pane.sourceId} not found in the EPI-Eval catalog.`}
      </div>
    );
  }

  return (
    <div className="space-y-3 p-3">
      <div className="flex flex-wrap items-center gap-2">
        <div className="flex items-center gap-1 rounded-md border border-white/10 bg-white/[0.02] p-1">
          <TabButton active={pane.tab === "graph"} onClick={() => setTab("graph")} icon={LineChart} label="Graph" />
          <TabButton active={pane.tab === "map"} onClick={() => setTab("map")} icon={Globe2} label="Map" />
        </div>
        {source.source_url && (
          <a
            href={source.source_url}
            target="_blank"
            rel="noreferrer"
            className="ml-auto flex items-center gap-1 text-xs text-sky-300 hover:text-sky-200"
          >
            Source <ExternalLink className="h-3 w-3" />
          </a>
        )}
      </div>

      {source.description && (
        <p className="text-xs leading-5 text-neutral-300">{source.description}</p>
      )}

      {slice.status === "loading" && (
        <div className="flex items-center gap-3 rounded-xl border border-white/10 bg-white/[0.03] px-5 py-6">
          <Loader2 className="h-6 w-6 shrink-0 animate-spin text-sky-400" aria-hidden="true" />
          <div>
            <p className="text-base font-semibold text-white">Fetching data from Huggingface…</p>
            <p className="text-xs text-neutral-400">Pulling rows for {source.pretty_name}.</p>
          </div>
        </div>
      )}
      {slice.status === "error" && (
        <div className="flex items-start justify-between gap-3 rounded-md border border-red-500/40 bg-red-950/20 px-3 py-2">
          <div className="text-sm text-red-200">
            <p className="font-semibold text-red-100">Failed to load.</p>
            <p className="mt-0.5 text-xs text-red-200/80">{slice.error}</p>
          </div>
          <button
            type="button"
            onClick={slice.refetch}
            className="flex shrink-0 items-center gap-1 rounded-md border border-red-300/50 bg-red-500/10 px-2.5 py-1 text-xs font-semibold text-red-100 transition hover:border-red-200 hover:bg-red-500/20"
          >
            <RefreshCw className="h-3 w-3" />
            Retry
          </button>
        </div>
      )}

      {slice.status === "ready" && slice.data && (
        <>
          {pane.tab === "graph" ? (
            <SourceTimelineChart source={source} rows={slice.data.rows} />
          ) : (
            <DatasetMap source={source} rows={slice.data.rows} />
          )}

          <div className="flex flex-wrap items-center justify-between gap-2 text-[11px] text-neutral-500">
            <span>
              {slice.data.truncated
                ? `Showing the first ${slice.data.rows.length.toLocaleString()} of ${slice.data.numRowsTotal.toLocaleString()} rows.`
                : `${slice.data.rows.length.toLocaleString()} rows.`}
            </span>
            <button
              type="button"
              onClick={() => setShowTable(!pane.showTable)}
              className="flex items-center gap-1 rounded border border-white/10 px-2 py-0.5 text-neutral-200 transition hover:border-sky-500 hover:text-sky-200"
            >
              <Table2 className="h-3 w-3" />
              {pane.showTable ? "Hide table" : "Show table"}
            </button>
          </div>

          {pane.showTable && <DataTable rows={slice.data.rows} filenameStem={source.id} />}
        </>
      )}
    </div>
  );
}

interface TabButtonProps {
  active: boolean;
  onClick: () => void;
  icon: ComponentType<SVGProps<SVGSVGElement>>;
  label: string;
}

function TabButton({ active, onClick, icon: Icon, label }: TabButtonProps) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={`flex items-center gap-1.5 rounded px-3 py-1.5 text-xs font-semibold transition ${
        active ? "bg-sky-700/40 text-sky-100" : "text-neutral-300 hover:bg-white/[0.05] hover:text-white"
      }`}
      aria-pressed={active}
    >
      <Icon className="h-3.5 w-3.5" />
      <span>{label}</span>
    </button>
  );
}
