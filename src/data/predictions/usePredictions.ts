import { useMemo } from "react";
import { useDatasetSlice } from "../hf/hooks";
import { companionRepoId, parsePredictionRows, type ParsedPredictions } from "./companion";

export interface PredictionsState {
  status: "idle" | "loading" | "ready" | "error";
  parsed: ParsedPredictions | null;
  error?: string;
  refetch: () => void;
}

/**
 * Fetches predictions from the EPI-Eval/<targetDatasetId>-predictions
 * companion repo and parses them into per-submitter groups.
 *
 * Returns idle if no targetDatasetId is provided. Caching, retry, and
 * concurrency gating come from the underlying useDatasetSlice. An empty
 * companion repo (no parquets yet) resolves to status="ready" with
 * `parsed.rows.length === 0` — distinct from "error" so the UI can show a
 * "no predictions submitted yet" affordance.
 */
export function usePredictionsForTarget(targetDatasetId: string | null): PredictionsState {
  const repoId = targetDatasetId ? companionRepoId(targetDatasetId) : null;
  const slice = useDatasetSlice(repoId);
  const parsed = useMemo(() => {
    if (slice.status !== "ready" || !slice.data) return null;
    return parsePredictionRows(slice.data.rows);
  }, [slice.status, slice.data]);

  return {
    status: slice.status,
    parsed,
    error: slice.error,
    refetch: slice.refetch
  };
}
