// Persistent (IndexedDB) store for user-uploaded prediction datasets.
// Datasets survive reloads. If IDB is unavailable (private browsing, etc.),
// the store falls back gracefully to in-memory only — the user just won't
// see their uploads after a reload.

import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import type { UserDataset } from "../data/predictions/types";
import { buildUserDataset, parseCsvText } from "../data/predictions/parser";
import { deleteDataset, loadAllDatasets, saveDataset } from "../data/predictions/storage";

interface PredictionsContextValue {
  datasets: UserDataset[];
  addDataset: (dataset: UserDataset) => void;
  removeDataset: (id: string) => void;
  getDataset: (id: string) => UserDataset | null;
}

const PredictionsContext = createContext<PredictionsContextValue | null>(null);

// On a brand-new install (no datasets in IDB and no seed flag), drop in the
// bundled sample forecast so the dashboard demos the whole compare-to flow
// without making the user hunt for a CSV. If the user deletes it, the flag
// keeps it from re-appearing on reload.
const SAMPLE_SEEDED_KEY = "epieval-sample-seeded";
const SAMPLE_PATH = "examples/sample-prediction.csv";
const SAMPLE_FILENAME = "sample-prediction.csv";

async function loadSampleDataset(): Promise<UserDataset | null> {
  try {
    const res = await fetch(SAMPLE_PATH);
    if (!res.ok) return null;
    const text = await res.text();
    const parsed = parseCsvText(text);
    if (parsed.parseErrors.length > 0) return null;
    const built = buildUserDataset(parsed, { filename: SAMPLE_FILENAME });
    return built.ok ? built.dataset : null;
  } catch {
    return null;
  }
}

function hasSampleSeeded(): boolean {
  try {
    return localStorage.getItem(SAMPLE_SEEDED_KEY) === "1";
  } catch {
    return false;
  }
}

function markSampleSeeded(): void {
  try {
    localStorage.setItem(SAMPLE_SEEDED_KEY, "1");
  } catch {
    /* localStorage unavailable — fine; we'll just re-seed next visit */
  }
}

export function PredictionsProvider({ children }: { children: ReactNode }) {
  const [datasets, setDatasets] = useState<UserDataset[]>([]);

  // Load persisted datasets on mount. If IDB is unavailable or empty,
  // we silently start with an empty list — same as the pre-Slice 3
  // behavior.
  useEffect(() => {
    let cancelled = false;
    loadAllDatasets()
      .then(async (loaded) => {
        if (cancelled) return;
        // Merge with anything added during the async load (race).
        setDatasets((curr) => {
          const ids = new Set(curr.map((d) => d.id));
          return [...curr, ...loaded.filter((d) => !ids.has(d.id))];
        });
        // First-launch sample seed: only when both IDB is empty and we've
        // never seeded before. Once seeded, the flag prevents re-adding —
        // so deleting the sample sticks across reloads.
        if (loaded.length === 0 && !hasSampleSeeded()) {
          const sample = await loadSampleDataset();
          if (cancelled || !sample) return;
          markSampleSeeded();
          setDatasets((curr) => [...curr, sample]);
          saveDataset(sample).catch((err) => {
            // eslint-disable-next-line no-console
            console.warn("Could not persist seeded sample:", err);
          });
        }
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
