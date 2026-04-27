import { useCallback, useEffect, useState } from "react";
import { getDatasetSlice, getRecentRows, type DatasetSlice, type RecentRowsResult } from "./rows";

export type AsyncState<T> = { status: "idle" | "loading" | "ready" | "error"; data: T | null; error?: string };
export type AsyncStateWithRefetch<T> = AsyncState<T> & { refetch: () => void };

export function useRecentRows(
  datasetId: string | null,
  n = 4,
  knownTotal?: number
): AsyncStateWithRefetch<RecentRowsResult> {
  const [state, setState] = useState<AsyncState<RecentRowsResult>>({ status: "idle", data: null });
  const [tick, setTick] = useState(0);
  const refetch = useCallback(() => setTick((t) => t + 1), []);

  useEffect(() => {
    if (!datasetId) {
      setState({ status: "idle", data: null });
      return;
    }
    let cancelled = false;
    setState({ status: "loading", data: null });
    // tick > 0 means user clicked Retry — bypass cache to actually re-hit HF.
    getRecentRows(datasetId, { n, knownTotal, force: tick > 0 })
      .then((r) => !cancelled && setState({ status: "ready", data: r }))
      .catch((e: Error) => !cancelled && setState({ status: "error", data: null, error: e.message }));
    return () => {
      cancelled = true;
    };
  }, [datasetId, n, knownTotal, tick]);

  return { ...state, refetch };
}

export function useDatasetSlice(datasetId: string | null): AsyncStateWithRefetch<DatasetSlice> {
  const [state, setState] = useState<AsyncState<DatasetSlice>>({ status: "idle", data: null });
  const [tick, setTick] = useState(0);
  const refetch = useCallback(() => setTick((t) => t + 1), []);

  useEffect(() => {
    if (!datasetId) {
      setState({ status: "idle", data: null });
      return;
    }
    let cancelled = false;
    setState({ status: "loading", data: null });
    getDatasetSlice(datasetId, { force: tick > 0 })
      .then((d) => !cancelled && setState({ status: "ready", data: d }))
      .catch((e: Error) => !cancelled && setState({ status: "error", data: null, error: e.message }));
    return () => {
      cancelled = true;
    };
  }, [datasetId, tick]);

  return { ...state, refetch };
}
