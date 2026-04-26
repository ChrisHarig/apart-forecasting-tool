import { Plus } from "lucide-react";
import { MAX_PANES, useWorkspace } from "../../state/WorkspaceContext";
import { WorkspaceGrid } from "../Workspace/WorkspaceGrid";

export function WorkspaceShell() {
  const { panes, addBrowserPane } = useWorkspace();
  const canAdd = panes.length < MAX_PANES;
  return (
    <div className="relative h-screen overflow-hidden bg-ink-950 text-white">
      <WorkspaceGrid />
      <button
        type="button"
        onClick={addBrowserPane}
        disabled={!canAdd}
        title={canAdd ? "Add another pane" : `Limit is ${MAX_PANES} panes`}
        aria-label="Add pane"
        className="absolute bottom-4 right-4 z-30 flex h-11 w-11 items-center justify-center rounded-full border border-white/15 bg-black/75 text-neutral-100 shadow-lg backdrop-blur transition hover:border-sky-500 hover:bg-black/90 hover:text-sky-200 disabled:cursor-not-allowed disabled:opacity-40"
      >
        <Plus className="h-5 w-5" />
      </button>
    </div>
  );
}
