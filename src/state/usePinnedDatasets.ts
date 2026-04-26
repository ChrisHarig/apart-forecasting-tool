// Persistent pinned-dataset set, scoped to the browser via localStorage.
//
// User-specific in the lightweight sense: stays with this browser/profile.
// We don't have user accounts yet, so localStorage is the right scope.
// Persists across page reloads, browser restarts, and EPI-Eval data updates
// — pin state is keyed on `source.id`, which is stable across re-ingests.

import { useCallback, useEffect, useState } from "react";

const STORAGE_KEY = "epi-eval:pinned-datasets:v1";

function readPinned(): string[] {
  if (typeof window === "undefined") return [];
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    if (!raw) return [];
    const parsed = JSON.parse(raw);
    if (!Array.isArray(parsed)) return [];
    return parsed.filter((x): x is string => typeof x === "string");
  } catch {
    return [];
  }
}

function writePinned(ids: string[]): void {
  if (typeof window === "undefined") return;
  try {
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(ids));
  } catch {
    // Quota errors are non-fatal — pinning is best-effort.
  }
}

export interface PinnedDatasetsApi {
  pinned: string[]; // ordered: oldest pin first (preserves user's pin order)
  isPinned: (id: string) => boolean;
  toggle: (id: string) => void;
  clear: () => void;
}

export function usePinnedDatasets(): PinnedDatasetsApi {
  const [pinned, setPinned] = useState<string[]>(() => readPinned());

  // Cross-tab sync: if another tab toggles a pin, mirror it here.
  useEffect(() => {
    const onStorage = (e: StorageEvent) => {
      if (e.key !== STORAGE_KEY) return;
      setPinned(readPinned());
    };
    window.addEventListener("storage", onStorage);
    return () => window.removeEventListener("storage", onStorage);
  }, []);

  const isPinned = useCallback((id: string) => pinned.includes(id), [pinned]);

  const toggle = useCallback(
    (id: string) => {
      setPinned((prev) => {
        const next = prev.includes(id) ? prev.filter((p) => p !== id) : [...prev, id];
        writePinned(next);
        return next;
      });
    },
    []
  );

  const clear = useCallback(() => {
    setPinned([]);
    writePinned([]);
  }, []);

  return { pinned, isPinned, toggle, clear };
}
