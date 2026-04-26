// Catalog state. The rest of the dashboard state (which datasets are open,
// which view, etc.) lives on WorkspaceContext now — this file is just the
// shared async fetch of the EPI-Eval HF org.

import { createContext, useCallback, useContext, useEffect, useState, type ReactNode } from "react";
import type { SourceMetadata } from "../types/source";
import { getCatalog } from "../data/hf/catalog";

type AsyncState<T> = { status: "idle" | "loading" | "ready" | "error"; data: T | null; error?: string };

interface DashboardContextValue {
  catalog: AsyncState<SourceMetadata[]>;
  refreshCatalog: () => void;
}

const DashboardContext = createContext<DashboardContextValue | null>(null);

export function DashboardProvider({ children }: { children: ReactNode }) {
  const [catalog, setCatalog] = useState<AsyncState<SourceMetadata[]>>({ status: "idle", data: null });

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

  const value: DashboardContextValue = { catalog, refreshCatalog };
  return <DashboardContext.Provider value={value}>{children}</DashboardContext.Provider>;
}

export function useDashboard(): DashboardContextValue {
  const ctx = useContext(DashboardContext);
  if (!ctx) throw new Error("useDashboard must be used within DashboardProvider");
  return ctx;
}
