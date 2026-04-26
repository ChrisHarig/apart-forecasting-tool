import { X } from "lucide-react";
import { useDashboard } from "../../state/DashboardContext";
import { useWorkspace, type Pane } from "../../state/WorkspaceContext";
import { BrowserBody } from "./BrowserBody";
import { ExplorerBody } from "../Explorer/ExplorerBody";

interface Props {
  pane: Pane;
}

export function PaneFrame({ pane }: Props) {
  const { closePane, focusPane, focusedPaneId } = useWorkspace();
  const { catalog } = useDashboard();
  const isFocused = focusedPaneId === pane.id;

  let title: React.ReactNode;
  if (pane.type === "browser") {
    title = <span className="text-sm font-medium text-white">Browse datasets</span>;
  } else {
    const source = catalog.data?.find((s) => s.id === pane.sourceId);
    title = (
      <div className="flex min-w-0 items-baseline gap-2">
        <span className="truncate text-sm font-medium text-white" title={source?.pretty_name}>
          {source?.pretty_name ?? pane.sourceId}
        </span>
        <span className="truncate font-mono text-[10px] text-neutral-500">{pane.sourceId}</span>
      </div>
    );
  }

  return (
    <div
      onClick={() => focusPane(pane.id)}
      className={`flex h-full min-h-0 flex-col overflow-hidden rounded-xl border bg-ink-900/40 transition-colors ${
        isFocused ? "border-sky-500/30" : "border-white/10"
      }`}
    >
      <div className="flex shrink-0 items-center gap-2 border-b border-white/10 bg-black/40 px-3 py-2">
        <div className="min-w-0 flex-1">{title}</div>
        <button
          type="button"
          onClick={(e) => {
            e.stopPropagation();
            closePane(pane.id);
          }}
          className="rounded p-1 text-neutral-400 transition hover:bg-white/10 hover:text-white"
          aria-label="Close pane"
          title="Close pane"
        >
          <X className="h-3.5 w-3.5" />
        </button>
      </div>
      <div className="min-h-0 flex-1 overflow-auto [scrollbar-gutter:stable]">
        {pane.type === "browser" ? <BrowserBody pane={pane} /> : <ExplorerBody pane={pane} />}
      </div>
    </div>
  );
}
