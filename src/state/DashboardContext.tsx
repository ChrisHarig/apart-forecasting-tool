import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import type { DashboardView } from "../types/dashboard";
import type { SourceMetadata } from "../types/source";
import type { NewsFeed } from "../types/news";
import { getCatalog } from "../data/hf/catalog";

const SELECTED_KEY = "epieval-dashboard:selected-source-ids";
const VIEW_KEY = "epieval-dashboard:view";
const SCROLL_TARGET_KEY = "epieval-dashboard:scroll-target";
const EXPLORER_SOURCE_KEY = "epieval-dashboard:explorer-source-id";

type AsyncState<T> = { status: "idle" | "loading" | "ready" | "error"; data: T | null; error?: string };

function loadJson<T>(key: string, fallback: T): T {
  try {
    const raw = window.localStorage.getItem(key);
    if (!raw) return fallback;
    return JSON.parse(raw) as T;
  } catch {
    return fallback;
  }
}

function saveJson<T>(key: string, value: T) {
  try {
    window.localStorage.setItem(key, JSON.stringify(value));
  } catch {
    /* ignore quota */
  }
}

interface DashboardContextValue {
  view: DashboardView;
  setView: (view: DashboardView) => void;

  catalog: AsyncState<SourceMetadata[]>;
  refreshCatalog: () => void;

  selectedSourceIds: string[];
  toggleSourceSelected: (id: string) => void;
  clearSelectedSources: () => void;

  // Cross-view navigation: clicking a source in the sidebar jumps to Feed and
  // tells the page to scroll/expand a specific dataset. Pages clear it after
  // consuming it so navigating back to Feed later doesn't re-trigger.
  scrollTargetId: string | null;
  setScrollTarget: (id: string | null) => void;

  // The Explorer view shows a single dataset full-screen. Set by Feed cards
  // when the user clicks "Open data".
  explorerSourceId: string | null;
  openExplorer: (sourceId: string) => void;
  setExplorerSource: (sourceId: string | null) => void;

  news: NewsFeed;
}

const DashboardContext = createContext<DashboardContextValue | null>(null);

export function DashboardProvider({ children }: { children: ReactNode }) {
  const [view, setViewState] = useState<DashboardView>(() => {
    const stored = loadJson<DashboardView | "sources" | "graph" | "map">(VIEW_KEY, "feed");
    // Old views may still be in localStorage from earlier builds.
    return stored === "feed" || stored === "explorer" || stored === "news" ? stored : "feed";
  });
  const [selectedSourceIds, setSelectedSourceIds] = useState<string[]>(() => loadJson<string[]>(SELECTED_KEY, []));
  const [scrollTargetId, setScrollTargetIdState] = useState<string | null>(() => loadJson<string | null>(SCROLL_TARGET_KEY, null));
  const [explorerSourceId, setExplorerSourceIdState] = useState<string | null>(() => loadJson<string | null>(EXPLORER_SOURCE_KEY, null));

  const [catalog, setCatalog] = useState<AsyncState<SourceMetadata[]>>({ status: "idle", data: null });

  const setView = useCallback((next: DashboardView) => {
    setViewState(next);
    saveJson(VIEW_KEY, next);
  }, []);

  const setScrollTarget = useCallback((id: string | null) => {
    setScrollTargetIdState(id);
    saveJson(SCROLL_TARGET_KEY, id);
  }, []);

  const setExplorerSource = useCallback((id: string | null) => {
    setExplorerSourceIdState(id);
    saveJson(EXPLORER_SOURCE_KEY, id);
  }, []);

  const openExplorer = useCallback((id: string) => {
    setExplorerSourceIdState(id);
    saveJson(EXPLORER_SOURCE_KEY, id);
    setViewState("explorer");
    saveJson(VIEW_KEY, "explorer");
  }, []);

  const refreshCatalog = useCallback(() => {
    setCatalog({ status: "loading", data: null });
    getCatalog({ force: true })
      .then((data) => setCatalog({ status: "ready", data }))
      .catch((error: Error) => setCatalog({ status: "error", data: null, error: error.message }));
  }, []);

  useEffect(() => {
    setCatalog({ status: "loading", data: null });
    getCatalog()
      .then((data) => setCatalog({ status: "ready", data }))
      .catch((error: Error) => setCatalog({ status: "error", data: null, error: error.message }));
  }, []);

  const toggleSourceSelected = useCallback((id: string) => {
    setSelectedSourceIds((current) => {
      const next = current.includes(id) ? current.filter((x) => x !== id) : [...current, id];
      saveJson(SELECTED_KEY, next);
      return next;
    });
  }, []);

  const clearSelectedSources = useCallback(() => {
    setSelectedSourceIds([]);
    saveJson(SELECTED_KEY, []);
  }, []);

  const news: NewsFeed = useMemo(() => ({ status: "ready", items: [], updatedAt: new Date().toISOString() }), []);

  const value: DashboardContextValue = {
    view,
    setView,
    catalog,
    refreshCatalog,
    selectedSourceIds,
    toggleSourceSelected,
    clearSelectedSources,
    scrollTargetId,
    setScrollTarget,
    explorerSourceId,
    openExplorer,
    setExplorerSource,
    news
  };

  return <DashboardContext.Provider value={value}>{children}</DashboardContext.Provider>;
}

export function useDashboard(): DashboardContextValue {
  const ctx = useContext(DashboardContext);
  if (!ctx) throw new Error("useDashboard must be used within DashboardProvider");
  return ctx;
}
