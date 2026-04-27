// Persistent (IndexedDB) store for user-uploaded prediction datasets.
// Datasets survive reloads. If IDB is unavailable (private browsing, etc.),
// the store falls back gracefully to in-memory only — the user just won't
// see their uploads after a reload.

import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import type { UserDataset } from "../data/predictions/types";
import { deleteDataset, loadAllDatasets, saveDataset } from "../data/predictions/storage";

interface PredictionsContextValue {
  datasets: UserDataset[];
  addDataset: (dataset: UserDataset) => void;
  removeDataset: (id: string) => void;
  getDataset: (id: string) => UserDataset | null;
}

const PredictionsContext = createContext<PredictionsContextValue | null>(null);

export function PredictionsProvider({ children }: { children: ReactNode }) {
  const [datasets, setDatasets] = useState<UserDataset[]>([]);

  // Load persisted datasets on mount. If IDB is unavailable or empty,
  // we silently start with an empty list — same as the pre-Slice 3
  // behavior.
  useEffect(() => {
    let cancelled = false;
    loadAllDatasets()
      .then((loaded) => {
        if (cancelled) return;
        // Merge with anything added during the async load (race).
        setDatasets((curr) => {
          const ids = new Set(curr.map((d) => d.id));
          return [...curr, ...loaded.filter((d) => !ids.has(d.id))];
        });
      })
      .catch((err) => {
        // eslint-disable-next-line no-console
        console.warn("Could not load predictions from IndexedDB:", err);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const addDataset = useCallback((dataset: UserDataset) => {
    setDatasets((curr) => [...curr, dataset]);
    saveDataset(dataset).catch((err) => {
      // eslint-disable-next-line no-console
      console.warn("Could not save prediction to IndexedDB:", err);
    });
  }, []);

  const removeDataset = useCallback((id: string) => {
    setDatasets((curr) => curr.filter((d) => d.id !== id));
    deleteDataset(id).catch((err) => {
      // eslint-disable-next-line no-console
      console.warn("Could not delete prediction from IndexedDB:", err);
    });
  }, []);

  const getDataset = useCallback(
    (id: string): UserDataset | null => datasets.find((d) => d.id === id) ?? null,
    [datasets]
  );

  const value = useMemo<PredictionsContextValue>(
    () => ({ datasets, addDataset, removeDataset, getDataset }),
    [datasets, addDataset, removeDataset, getDataset]
  );

  return <PredictionsContext.Provider value={value}>{children}</PredictionsContext.Provider>;
}

export function usePredictions(): PredictionsContextValue {
  const ctx = useContext(PredictionsContext);
  if (!ctx) throw new Error("usePredictions must be used within PredictionsProvider");
  return ctx;
}
