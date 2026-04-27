// Workspace state for the multi-pane explorer. A workspace is an ordered
// list of 1..MAX_PANES panes. Each pane is either a browser (the dataset
// catalog) or an explorer (one specific dataset). Browsing is the default
// state — fresh sessions and cleared workspaces always have at least one
// browser pane open.
//
// Phase 1: this context provides the state model and persistence; nothing
// in the UI consumes it yet. Subsequent phases swap it in for the existing
// DashboardContext-driven view + explorerSourceId state.

import { createContext, useCallback, useContext, useEffect, useState, type ReactNode } from "react";

export const MAX_PANES = 4;
const STORAGE_KEY = "epieval-workspace:v1";

// ─── Pane types ────────────────────────────────────────────────────────────

export interface BrowserPane {
  id: string;
  type: "browser";
  // Pane-local UI state for the dataset catalog. Search query persists per
  // pane so two side-by-side browsers don't fight over a global query.
  query: string;
}

export interface ExplorerChartState {
  metric: string | null;
  filters: { name: string; value: string }[];
  groupBy: string; // "__none__" or a column name
  // null → show all groups (or the auto-defaulted top N when group count exceeds the cap)
  visibleSeries: string[] | null;
}

export interface ExplorerMapState {
  metric: string | null;
  startIdx: number;
  endIdx: number;
  dateIdx: number;
  isPlaying: boolean;
  speedMs: number;
  // Active level key (level::boundaryType). The map auto-detects on first
  // render; saving the chosen level lets a reload restore the user's pick.
  levelKey: string | null;
  // Soft selection on the boundary map (a country / state / county the user clicked).
  selectedId: string | null;
  selectedName: string | null;
}

export interface ExplorerPane {
  id: string;
  type: "explorer";
  sourceId: string;
  tab: "graph" | "map";
  chart: ExplorerChartState;
  map: ExplorerMapState;
  showTable: boolean;
}

// User-uploaded prediction (or plain dataset). `targetSourceId === null`
// is the view-only mode — the user just wants to see their data. When set,
// the pane compares against that EPI-Eval dataset's `targetColumn`.
export interface UserDatasetPane {
  id: string;
  type: "user-dataset";
  userDatasetId: string;
  targetSourceId: string | null;
  targetColumn: string | null;
  showTable: boolean;
}

export type Pane = BrowserPane | ExplorerPane | UserDatasetPane;

export interface WorkspaceState {
  panes: Pane[]; // length 1..MAX_PANES, never 0
  focusedPaneId: string;
}

// ─── Defaults / constructors ──────────────────────────────────────────────

function generatePaneId(): string {
  return `pane-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
}

function defaultChart(): ExplorerChartState {
  return { metric: null, filters: [], groupBy: "__none__", visibleSeries: null };
}

function defaultMap(): ExplorerMapState {
  return {
    metric: null,
    startIdx: 0,
    endIdx: 0,
    dateIdx: 0,
    isPlaying: false,
    speedMs: 250,
    levelKey: null,
    selectedId: null,
    selectedName: null
  };
}

export function makeBrowserPane(opts: { id?: string; query?: string } = {}): BrowserPane {
  return { id: opts.id ?? generatePaneId(), type: "browser", query: opts.query ?? "" };
}

export function makeExplorerPane(sourceId: string, opts: { id?: string } = {}): ExplorerPane {
  return {
    id: opts.id ?? generatePaneId(),
    type: "explorer",
    sourceId,
    tab: "graph",
    chart: defaultChart(),
    map: defaultMap(),
    showTable: true
  };
}

export function makeUserDatasetPane(
  userDatasetId: string,
  opts: { id?: string } = {}
): UserDatasetPane {
  return {
    id: opts.id ?? generatePaneId(),
    type: "user-dataset",
    userDatasetId,
    targetSourceId: null,
    targetColumn: null,
    showTable: true
  };
}

// ─── Persistence ──────────────────────────────────────────────────────────

function isPane(value: unknown): value is Pane {
  if (!value || typeof value !== "object") return false;
  const v = value as Record<string, unknown>;
  if (typeof v.id !== "string") return false;
  if (v.type === "browser") return typeof v.query === "string";
  if (v.type === "explorer") {
    return typeof v.sourceId === "string" && (v.tab === "graph" || v.tab === "map");
  }
  if (v.type === "user-dataset") {
    return typeof v.userDatasetId === "string";
  }
  return false;
}

function loadPersistedState(): WorkspaceState {
  const fallback: WorkspaceState = (() => {
    const pane = makeBrowserPane();
    return { panes: [pane], focusedPaneId: pane.id };
  })();

  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    if (!raw) return fallback;
    const parsed = JSON.parse(raw) as Partial<WorkspaceState> | null;
    if (!parsed || !Array.isArray(parsed.panes)) return fallback;
    const panes = parsed.panes.filter(isPane).slice(0, MAX_PANES);
    if (panes.length === 0) return fallback;
    const focusedPaneId =
      typeof parsed.focusedPaneId === "string" && panes.some((p) => p.id === parsed.focusedPaneId)
        ? parsed.focusedPaneId
        : panes[0].id;
    return { panes, focusedPaneId };
  } catch {
    return fallback;
  }
}

function persist(state: WorkspaceState): void {
  try {
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(state));
  } catch {
    // Quota exceeded or storage unavailable — best effort.
  }
}

// ─── Context ──────────────────────────────────────────────────────────────

interface WorkspaceContextValue {
  panes: Pane[];
  focusedPaneId: string;

  // Adds a fresh browser pane. No-op when already at MAX_PANES.
  addBrowserPane: () => void;

  // Closes a pane. Closing the last remaining pane resets it to a fresh
  // browser pane (so the workspace is never empty).
  closePane: (id: string) => void;

  // Converts a pane to an explorer for the given source. Used when the
  // user clicks "Open data" on a card *inside* a browser pane (so that
  // pane transforms in place) — and also when something else wants to
  // promote a brand-new explorer (we'll add a new pane in that case).
  openExplorerInPane: (paneId: string, sourceId: string) => void;

  // Converts a pane to a user-dataset view for the given uploaded dataset.
  // Same in-place transform as openExplorerInPane.
  openUserDatasetInPane: (paneId: string, userDatasetId: string) => void;

  // Convenience: given a sourceId, either convert the focused browser
  // pane (if there is one) or append a new explorer pane.
  openExplorer: (sourceId: string) => void;

  focusPane: (id: string) => void;

  // Update a pane's mutable fields. Fills the role today's per-component
  // useState hooks play; we'll wire components to use this in phase 4.
  updatePane: (id: string, updater: (p: Pane) => Pane) => void;

  // Resets the workspace to a single browser pane.
  resetWorkspace: () => void;
}

const WorkspaceContext = createContext<WorkspaceContextValue | null>(null);

export function WorkspaceProvider({ children }: { children: ReactNode }) {
  const [state, setState] = useState<WorkspaceState>(loadPersistedState);

  useEffect(() => {
    persist(state);
  }, [state]);

  const addBrowserPane = useCallback(() => {
    setState((curr) => {
      if (curr.panes.length >= MAX_PANES) return curr;
      const pane = makeBrowserPane();
      return { panes: [...curr.panes, pane], focusedPaneId: pane.id };
    });
  }, []);

  const closePane = useCallback((id: string) => {
    setState((curr) => {
      if (curr.panes.length <= 1) {
        const pane = makeBrowserPane();
        return { panes: [pane], focusedPaneId: pane.id };
      }
      const idx = curr.panes.findIndex((p) => p.id === id);
      if (idx < 0) return curr;
      const nextPanes = curr.panes.filter((p) => p.id !== id);
      const nextFocusedPaneId =
        curr.focusedPaneId === id ? nextPanes[Math.max(0, idx - 1)].id : curr.focusedPaneId;
      return { panes: nextPanes, focusedPaneId: nextFocusedPaneId };
    });
  }, []);

  const openExplorerInPane = useCallback((paneId: string, sourceId: string) => {
    setState((curr) => {
      if (!curr.panes.some((p) => p.id === paneId)) return curr;
      return {
        panes: curr.panes.map((p) => (p.id === paneId ? makeExplorerPane(sourceId, { id: paneId }) : p)),
        focusedPaneId: paneId
      };
    });
  }, []);

  const openUserDatasetInPane = useCallback((paneId: string, userDatasetId: string) => {
    setState((curr) => {
      if (!curr.panes.some((p) => p.id === paneId)) return curr;
      return {
        panes: curr.panes.map((p) =>
          p.id === paneId ? makeUserDatasetPane(userDatasetId, { id: paneId }) : p
        ),
        focusedPaneId: paneId
      };
    });
  }, []);

  const openExplorer = useCallback((sourceId: string) => {
    setState((curr) => {
      // If the focused pane is a browser, transform it in place.
      const focused = curr.panes.find((p) => p.id === curr.focusedPaneId);
      if (focused && focused.type === "browser") {
        return {
          panes: curr.panes.map((p) =>
            p.id === focused.id ? makeExplorerPane(sourceId, { id: focused.id }) : p
          ),
          focusedPaneId: focused.id
        };
      }
      // Otherwise append a new explorer pane (if room).
      if (curr.panes.length >= MAX_PANES) return curr;
      const newPane = makeExplorerPane(sourceId);
      return { panes: [...curr.panes, newPane], focusedPaneId: newPane.id };
    });
  }, []);

  const focusPane = useCallback((id: string) => {
    setState((curr) => (curr.panes.some((p) => p.id === id) ? { ...curr, focusedPaneId: id } : curr));
  }, []);

  const updatePane = useCallback((id: string, updater: (p: Pane) => Pane) => {
    setState((curr) => ({
      ...curr,
      panes: curr.panes.map((p) => (p.id === id ? updater(p) : p))
    }));
  }, []);

  const resetWorkspace = useCallback(() => {
    const pane = makeBrowserPane();
    setState({ panes: [pane], focusedPaneId: pane.id });
  }, []);

  const value: WorkspaceContextValue = {
    panes: state.panes,
    focusedPaneId: state.focusedPaneId,
    addBrowserPane,
    closePane,
    openExplorerInPane,
    openUserDatasetInPane,
    openExplorer,
    focusPane,
    updatePane,
    resetWorkspace
  };

  return <WorkspaceContext.Provider value={value}>{children}</WorkspaceContext.Provider>;
}

export function useWorkspace(): WorkspaceContextValue {
  const ctx = useContext(WorkspaceContext);
  if (!ctx) throw new Error("useWorkspace must be used within WorkspaceProvider");
  return ctx;
}
