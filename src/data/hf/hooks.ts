import { useEffect, useState } from "react";
import { getDatasetSlice, getRecentRows, type DatasetSlice, type RecentRowsResult } from "./rows";

export type AsyncState<T> = { status: "idle" | "loading" | "ready" | "error"; data: T | null; error?: string };

export function useRecentRows(datasetId: string | null, n = 4, knownTotal?: number): AsyncState<RecentRowsResult> {
  const [state, setState] = useState<AsyncState<RecentRowsResult>>({ status: "idle", data: null });

  useEffect(() => {
    if (!datasetId) {
      setState({ status: "idle", data: null });
      return;
    }
    let cancelled = false;
    setState({ status: "loading", data: null });
    getRecentRows(datasetId, { n, knownTotal })
      .then((r) => !cancelled && setState({ status: "ready", data: r }))
      .catch((e: Error) => !cancelled && setState({ status: "error", data: null, error: e.message }));
    return () => {
      cancelled = true;
    };
  }, [datasetId, n, knownTotal]);

  return state;
}

export function useDatasetSlice(datasetId: string | null): AsyncState<DatasetSlice> {
  const [state, setState] = useState<AsyncState<DatasetSlice>>({ status: "idle", data: null });

  useEffect(() => {
    if (!datasetId) {
      setState({ status: "idle", data: null });
      return;
    }
    let cancelled = false;
    setState({ status: "loading", data: null });
    getDatasetSlice(datasetId)
      .then((d) => !cancelled && setState({ status: "ready", data: d }))
      .catch((e: Error) => !cancelled && setState({ status: "error", data: null, error: e.message }));
    return () => {
      cancelled = true;
    };
  }, [datasetId]);

  return state;
}
