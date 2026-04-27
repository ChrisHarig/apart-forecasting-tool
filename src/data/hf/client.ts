// Thin fetch wrappers for the Huggingface APIs we hit from the browser.
// EPI-Eval datasets live under the EPI-Eval org. cardData on /api/datasets is the
// parsed YAML frontmatter, so we don't need a YAML parser in the browser.

import { withGate } from "./concurrency";

export const EPI_EVAL_ORG = "EPI-Eval";

const HF_API = "https://huggingface.co/api";
const HF_DSERVER = "https://datasets-server.huggingface.co";

const TOKEN = (import.meta.env.VITE_HF_TOKEN as string | undefined)?.trim() || undefined;

function authHeaders(): HeadersInit {
  return TOKEN ? { Authorization: `Bearer ${TOKEN}` } : {};
}

export interface HfDatasetInfo {
  id: string;
  lastModified?: string;
  cardData?: Record<string, unknown>;
  tags?: string[];
}

export async function listOrgDatasets(org = EPI_EVAL_ORG): Promise<HfDatasetInfo[]> {
  return withGate(async () => {
    const res = await fetch(`${HF_API}/datasets?author=${encodeURIComponent(org)}&full=true`, {
      headers: authHeaders()
    });
    if (!res.ok) throw new Error(`HF list datasets failed: ${res.status} ${res.statusText}`);
    return res.json();
  });
}

export interface HfRowsResponse {
  features: Array<{ feature_idx: number; name: string; type: { dtype?: string; _type?: string } }>;
  rows: Array<{ row_idx: number; row: Record<string, unknown> }>;
  num_rows_total: number;
  num_rows_per_page: number;
}

export async function fetchRows(
  datasetId: string,
  opts: { config?: string; split?: string; offset?: number; length?: number } = {}
): Promise<HfRowsResponse> {
  const params = new URLSearchParams({
    dataset: datasetId,
    config: opts.config ?? "default",
    split: opts.split ?? "train",
    offset: String(opts.offset ?? 0),
    length: String(opts.length ?? 100)
  });
  return withGate(async () => {
    const res = await fetch(`${HF_DSERVER}/rows?${params.toString()}`, { headers: authHeaders() });
    if (!res.ok) {
      const detail = res.status === 429 ? " (rate-limited — set VITE_HF_TOKEN in .env for higher limits)" : "";
      throw new Error(`HF rows failed: ${res.status} ${res.statusText}${detail}`);
    }
    return res.json();
  });
}

export interface HfSplitsResponse {
  splits: Array<{ dataset: string; config: string; split: string; num_bytes?: number; num_examples?: number }>;
}

export async function fetchSplits(datasetId: string): Promise<HfSplitsResponse> {
  const params = new URLSearchParams({ dataset: datasetId });
  return withGate(async () => {
    const res = await fetch(`${HF_DSERVER}/splits?${params.toString()}`, { headers: authHeaders() });
    if (!res.ok) throw new Error(`HF splits failed: ${res.status} ${res.statusText}`);
    return res.json();
  });
}

export function hasHfToken(): boolean {
  return Boolean(TOKEN);
}
