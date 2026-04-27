import { useMemo, useState } from "react";
import {
  ArrowUpRight,
  ChevronDown,
  ChevronRight,
  ExternalLink,
  Pin,
  RefreshCw,
  Search,
  Trash2
} from "lucide-react";
import { useDashboard } from "../../state/DashboardContext";
import { usePredictions } from "../../state/PredictionsContext";
import { useRecentRows } from "../../data/hf/hooks";
import { usePinnedDatasets, type PinnedDatasetsApi } from "../../state/usePinnedDatasets";
import type { DatasetRow, RecentRowsResult } from "../../data/hf/rows";
import type { SourceMetadata } from "../../types/source";
import type { UserDataset } from "../../data/predictions/types";
import { UploadZone } from "../Predictions/UploadZone";

const STALE_THRESHOLD_DAYS = 90;

type FeedItem =
  | { kind: "user"; dataset: UserDataset }
  | { kind: "epi"; source: SourceMetadata };

interface FeedPageProps {
  onOpen: (sourceId: string) => void;
  onOpenUserDataset: (userDatasetId: string) => void;
}

export function FeedPage({ onOpen, onOpenUserDataset }: FeedPageProps) {
  const { catalog, refreshCatalog } = useDashboard();
  const { datasets, removeDataset } = usePredictions();
  const [query, setQuery] = useState("");
  const pin = usePinnedDatasets();

  const visibleItems: FeedItem[] = useMemo(() => {
    const out: FeedItem[] = [];

    // User datasets first, newest upload first; filterable by filename.
    const userMatches = !query
      ? [...datasets]
      : datasets.filter((d) =>
          d.filename.toLowerCase().includes(query.toLowerCase())
        );
    userMatches.sort((a, b) => b.uploadedAt - a.uploadedAt);
    for (const d of userMatches) out.push({ kind: "user", dataset: d });

    // EPI-Eval next, with the existing pin-first ordering.
    if (catalog.data) {
      const filtered = !query
        ? catalog.data
        : catalog.data.filter((s) =>
            [s.pretty_name, s.id, s.description ?? "", s.notes_general ?? "", s.pathogens.join(" ")]
              .join(" ")
              .toLowerCase()
              .includes(query.toLowerCase())
          );
      if (pin.pinned.length === 0) {
        for (const s of filtered) out.push({ kind: "epi", source: s });
      } else {
        const pinnedSet = new Set(pin.pinned);
        const indexById = new Map(filtered.map((s, i) => [s.id, i]));
        const pinnedRows = pin.pinned
          .map((id) => filtered.find((s) => s.id === id))
          .filter((s): s is SourceMetadata => Boolean(s));
        const rest = filtered.filter((s) => !pinnedSet.has(s.id));
        rest.sort((a, b) => (indexById.get(a.id) ?? 0) - (indexById.get(b.id) ?? 0));
        for (const s of pinnedRows) out.push({ kind: "epi", source: s });
        for (const s of rest) out.push({ kind: "epi", source: s });
      }
    }

    return out;
  }, [catalog.data, query, pin.pinned, datasets]);

  return (
    <div className="space-y-3 p-3">
      <header className="flex flex-wrap items-center gap-3 rounded-xl border border-white/10 bg-black/60 px-4 py-2.5">
        <div className="flex items-baseline gap-2">
          <h1 className="text-sm font-semibold text-white">EPI-Eval datasets</h1>
          <a
            href="https://huggingface.co/EPI-Eval"
            target="_blank"
            rel="noreferrer"
            className="text-xs text-neutral-400 hover:text-sky-200"
          >
            huggingface.co/EPI-Eval
          </a>
          {catalog.data && (
            <span className="text-xs text-neutral-500">· {catalog.data.length}</span>
          )}
          {datasets.length > 0 && (
            <span className="text-xs text-amber-300">· {datasets.length} mine</span>
          )}
        </div>
        <div className="relative ml-auto min-w-[220px] flex-1 max-w-md">
          <Search className="pointer-events-none absolute left-3 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-neutral-500" />
          <input
            type="search"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Search by name, pathogen, geography…"
            className="w-full rounded-md border border-white/10 bg-white/[0.03] py-1.5 pl-8 pr-3 text-xs text-white placeholder:text-neutral-500 focus:border-sky-500 focus:outline-none"
          />
        </div>
        <UploadZone onUploaded={onOpenUserDataset} />
        <button
          type="button"
          onClick={refreshCatalog}
          className="flex items-center gap-1 rounded-md border border-white/15 px-2 py-1 text-xs text-neutral-200 hover:border-sky-500 hover:text-sky-200"
          title="Refresh catalog"
        >
          <RefreshCw className="h-3 w-3" /> Refresh
        </button>
      </header>

      {catalog.status === "loading" && (
        <div className="rounded-xl border border-white/10 bg-white/[0.03] p-4 text-sm text-neutral-300">
          Loading catalog from Huggingface…
        </div>
      )}
      {catalog.status === "error" && (
        <div className="rounded-xl border border-red-500/40 bg-red-950/20 p-4 text-sm text-red-200">
          <p className="font-semibold">Could not load catalog</p>
          <p className="mt-1 text-red-200/80">{catalog.error}</p>
          <p className="mt-2 text-xs text-red-200/60">
            If EPI-Eval datasets are private, set <code className="font-mono">VITE_HF_TOKEN</code> in <code>.env</code>.
          </p>
        </div>
      )}

      {visibleItems.length === 0 && catalog.status === "ready" && (
        <div className="rounded-xl border border-white/10 bg-white/[0.03] p-4 text-sm text-neutral-300">
          No datasets match.
        </div>
      )}

      {visibleItems.length > 0 && (
        <ul className="space-y-1.5">
          {visibleItems.map((item) =>
            item.kind === "user" ? (
              <UserDatasetCard
                key={item.dataset.id}
                dataset={item.dataset}
                onOpen={onOpenUserDataset}
                onRemove={removeDataset}
              />
            ) : (
              <DatasetCard
                key={item.source.id}
                source={item.source}
                onOpen={onOpen}
                pin={pin}
              />
            )
          )}
        </ul>
      )}
    </div>
  );
}

interface CardProps {
  source: SourceMetadata;
  onOpen: (sourceId: string) => void;
  pin: PinnedDatasetsApi;
}

function DatasetCard({ source, onOpen, pin }: CardProps) {
  const [expanded, setExpanded] = useState(false);
  // Only fetch the per-card row preview when the user actually expands the
  // card. Pre-expansion, the LiveBadge falls through to `time_coverage.end`
  // from card metadata — no network request needed.
  const recent = useRecentRows(expanded ? source.id : null, 5, source.computed?.row_count);
  const live = useMemo(() => isLive(source, recent.data), [source, recent.data]);
  const pinned = pin.isPinned(source.id);
  const hfDatasetUrl = `https://huggingface.co/datasets/${source.id}`;

  const metaPills: string[] = [];
  if (source.cadence) metaPills.push(source.cadence);
  if (source.surveillance_category !== "none") metaPills.push(source.surveillance_category);
  if (source.pathogens.length > 0) metaPills.push(source.pathogens.slice(0, 2).join("·"));
  if (source.geography_countries.length > 0) metaPills.push(source.geography_countries.slice(0, 2).join("·"));

  return (
    <li
      className={`rounded-lg border bg-white/[0.03] ${
        pinned ? "border-sky-500/40 bg-sky-500/[0.04]" : "border-white/10"
      }`}
    >
      <div
        role="button"
        tabIndex={0}
        onClick={() => setExpanded((v) => !v)}
        onKeyDown={(e) => {
          if (e.key === "Enter" || e.key === " ") {
            e.preventDefault();
            setExpanded((v) => !v);
          }
        }}
        aria-expanded={expanded}
        className="flex cursor-pointer items-center gap-x-3 rounded-lg px-3 py-2 transition hover:bg-white/[0.02]"
      >
        <span className="shrink-0 rounded p-0.5 text-neutral-400" aria-hidden="true">
          {expanded ? <ChevronDown className="h-3.5 w-3.5" /> : <ChevronRight className="h-3.5 w-3.5" />}
        </span>

        <button
          type="button"
          onClick={(e) => {
            e.stopPropagation();
            pin.toggle(source.id);
          }}
          className={`shrink-0 rounded p-1 transition ${
            pinned
              ? "text-sky-300 hover:text-sky-100"
              : "text-neutral-500 hover:text-sky-300"
          }`}
          title={pinned ? "Unpin from top" : "Pin to top"}
          aria-pressed={pinned}
        >
          {pinned ? <Pin className="h-3.5 w-3.5 fill-current" /> : <Pin className="h-3.5 w-3.5" />}
        </button>

        <div className="flex min-w-0 flex-1 items-center gap-2">
          <h3 className="truncate text-sm font-semibold text-white" title={source.pretty_name}>
            {source.pretty_name}
          </h3>
          <span className="shrink-0">
            <LiveBadge live={live} latestDate={recent.data?.latestDate ?? deriveCardEnd(source)} />
          </span>
          <span className="hidden truncate font-mono text-[10px] text-neutral-500 sm:inline" title={source.id}>
            {source.id}
          </span>
        </div>

        {metaPills.length > 0 && (
          <span className="hidden shrink-0 text-[11px] text-neutral-400 lg:inline">{metaPills.join(" · ")}</span>
        )}

        <div className="flex shrink-0 items-center gap-1.5">
          <a
            href={hfDatasetUrl}
            target="_blank"
            rel="noreferrer"
            onClick={(e) => e.stopPropagation()}
            className="flex items-center gap-1 rounded-md border border-white/10 px-2 py-0.5 text-[11px] text-neutral-200 hover:border-sky-500 hover:text-sky-200"
            title={`Open ${source.id} on HuggingFace`}
          >
            HF <ExternalLink className="h-3 w-3" />
          </a>
          {source.source_url && (
            <a
              href={source.source_url}
              target="_blank"
              rel="noreferrer"
              onClick={(e) => e.stopPropagation()}
              className="flex items-center gap-1 rounded-md border border-white/10 px-2 py-0.5 text-[11px] text-neutral-200 hover:border-sky-500 hover:text-sky-200"
              title="Open the upstream source"
            >
              Source <ExternalLink className="h-3 w-3" />
            </a>
          )}
          <button
            type="button"
            onClick={(e) => {
              e.stopPropagation();
              onOpen(source.id);
            }}
            className="flex items-center gap-1 rounded-md border border-sky-500/40 bg-sky-700/30 px-2 py-0.5 text-[11px] font-semibold text-sky-100 hover:border-sky-500/60 hover:bg-sky-700/45"
            title="Open in this pane"
          >
            Open data <ArrowUpRight className="h-3 w-3" />
          </button>
        </div>
      </div>

      {expanded && (
        <div className="border-t border-white/10 px-4 py-3">
          {source.description && <p className="text-xs leading-5 text-neutral-300">{source.description}</p>}
          <div className="mt-2 flex flex-wrap gap-1.5 text-[10px] text-neutral-300">
            {source.cadence && <Tag>{source.cadence}</Tag>}
            {source.surveillance_category !== "none" && <Tag>{source.surveillance_category}</Tag>}
            {source.pathogens.slice(0, 4).map((p) => (
              <Tag key={p}>{p}</Tag>
            ))}
            {source.geography_countries.slice(0, 4).map((c) => (
              <Tag key={c}>{c}</Tag>
            ))}
          </div>
          <div className="mt-3">
            <RecentObservationsTable recent={recent} />
          </div>
        </div>
      )}
    </li>
  );
}

interface UserCardProps {
  dataset: UserDataset;
  onOpen: (id: string) => void;
  onRemove: (id: string) => void;
}

function UserDatasetCard({ dataset, onOpen, onRemove }: UserCardProps) {
  const [expanded, setExpanded] = useState(false);
  const previewRows = dataset.rows.slice(0, 5);
  const previewColumns = useMemo(() => {
    const seen = new Set<string>();
    const cols: string[] = [];
    for (const r of previewRows) for (const k of Object.keys(r)) if (!seen.has(k)) (seen.add(k), cols.push(k));
    return cols;
  }, [previewRows]);

  return (
    <li className="rounded-lg border border-amber-500/30 bg-amber-500/[0.03]">
      <div
        role="button"
        tabIndex={0}
        onClick={() => setExpanded((v) => !v)}
        onKeyDown={(e) => {
          if (e.key === "Enter" || e.key === " ") {
            e.preventDefault();
            setExpanded((v) => !v);
          }
        }}
        aria-expanded={expanded}
        className="flex cursor-pointer items-center gap-x-3 rounded-lg px-3 py-2 transition hover:bg-white/[0.02]"
      >
        <span className="shrink-0 rounded p-0.5 text-neutral-400" aria-hidden="true">
          {expanded ? <ChevronDown className="h-3.5 w-3.5" /> : <ChevronRight className="h-3.5 w-3.5" />}
        </span>

        <div className="flex min-w-0 flex-1 items-center gap-2">
          <h3 className="truncate text-sm font-semibold text-white" title={dataset.filename}>
            {dataset.filename}
          </h3>
          <span className="shrink-0 rounded-full border border-amber-500/40 bg-amber-700/20 px-2 py-0.5 text-[10px] font-semibold text-amber-100">
            Personal
          </span>
          <span className="hidden truncate font-mono text-[10px] text-neutral-500 sm:inline">
            {dataset.rowCount.toLocaleString()} rows · uploaded{" "}
            {new Date(dataset.uploadedAt).toLocaleTimeString(undefined, {
              hour: "numeric",
              minute: "2-digit"
            })}
          </span>
        </div>

        <span className="hidden shrink-0 text-[11px] text-neutral-400 lg:inline">
          {dataset.numericFields.length} numeric
          {dataset.quantileField && " · quantile"}
        </span>

        <div className="flex shrink-0 items-center gap-1.5">
          <button
            type="button"
            onClick={(e) => {
              e.stopPropagation();
              onRemove(dataset.id);
            }}
            className="rounded p-1 text-neutral-500 transition hover:bg-white/10 hover:text-red-300"
            title="Remove"
            aria-label={`Remove ${dataset.filename}`}
          >
            <Trash2 className="h-3.5 w-3.5" />
          </button>
          <button
            type="button"
            onClick={(e) => {
              e.stopPropagation();
              onOpen(dataset.id);
            }}
            className="flex items-center gap-1 rounded-md border border-sky-500/40 bg-sky-700/30 px-2 py-0.5 text-[11px] font-semibold text-sky-100 hover:border-sky-500/60 hover:bg-sky-700/45"
            title="Open in this pane"
          >
            Open <ArrowUpRight className="h-3 w-3" />
          </button>
        </div>
      </div>

      {expanded && (
        <div className="border-t border-white/10 px-4 py-3">
          <div className="mt-1 flex flex-wrap gap-1.5 text-[10px] text-neutral-300">
            <Tag>date: {dataset.dateField}</Tag>
            {dataset.numericFields.slice(0, 4).map((f) => (
              <Tag key={f}>numeric: {f}</Tag>
            ))}
          </div>
          <div className="mt-3">
            <PreviewRowsTable rows={previewRows} columns={previewColumns} />
          </div>
        </div>
      )}
    </li>
  );
}

function PreviewRowsTable({ rows, columns }: { rows: DatasetRow[]; columns: string[] }) {
  if (rows.length === 0) {
    return (
      <div className="rounded-md border border-white/5 bg-black/30 px-3 py-2 text-xs text-neutral-500">
        No rows.
      </div>
    );
  }
  return (
    <div className="rounded-md border border-white/10 bg-black/40">
      <p className="border-b border-white/5 px-3 py-1.5 text-[10px] font-semibold uppercase tracking-wider text-neutral-400">
        First {rows.length} rows
      </p>
      <div className="overflow-x-auto scrollbar-hidden">
        <table className="w-full min-w-max text-xs">
          <thead className="bg-white/[0.03] text-[10px] uppercase text-neutral-500">
            <tr>
              {columns.map((k) => (
                <th key={k} className="whitespace-nowrap px-3 py-1.5 text-left font-semibold">
                  {k}
                </th>
              ))}
            </tr>
          </thead>
          <tbody className="divide-y divide-white/5">
            {rows.map((row, i) => (
              <tr key={i}>
                {columns.map((k) => (
                  <td key={k} className="whitespace-nowrap px-3 py-2 text-neutral-200">
                    {formatCell(row[k])}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function RecentObservationsTable({ recent }: { recent: ReturnType<typeof useRecentRows> }) {
  if (recent.status === "loading") {
    return (
      <div className="rounded-md border border-white/5 bg-black/30 px-3 py-2 text-xs text-neutral-500">
        Loading recent observations…
      </div>
    );
  }
  if (recent.status === "error") {
    return (
      <div className="rounded-md border border-red-500/30 bg-red-950/20 px-3 py-2 text-xs text-red-200">
        Couldn't load recent observations: {recent.error}
      </div>
    );
  }
  const rows = recent.data?.rows ?? [];
  if (rows.length === 0) {
    return (
      <div className="rounded-md border border-white/5 bg-black/30 px-3 py-2 text-xs text-neutral-500">
        No rows in this dataset yet.
      </div>
    );
  }

  const columns: string[] = [];
  const seen = new Set<string>();
  for (const r of rows) for (const k of Object.keys(r)) if (!seen.has(k)) (seen.add(k), columns.push(k));

  return (
    <div className="rounded-md border border-white/10 bg-black/40">
      <p className="border-b border-white/5 px-3 py-1.5 text-[10px] font-semibold uppercase tracking-wider text-neutral-400">
        Recent observations
      </p>
      <div className="overflow-x-auto scrollbar-hidden">
        <table className="w-full min-w-max text-xs">
          <thead className="bg-white/[0.03] text-[10px] uppercase text-neutral-500">
            <tr>
              {columns.map((k) => (
                <th key={k} className="whitespace-nowrap px-3 py-1.5 text-left font-semibold">
                  {k}
                </th>
              ))}
            </tr>
          </thead>
          <tbody className="divide-y divide-white/5">
            {rows.map((row, i) => (
              <tr key={i}>
                {columns.map((k) => (
                  <td key={k} className="whitespace-nowrap px-3 py-2 text-neutral-200">
                    {formatCell(row[k])}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function LiveBadge({ live, latestDate }: { live: "live" | "stale" | "unknown"; latestDate: string | null }) {
  if (!latestDate) return null;
  const dateLabel = latestDate.slice(0, 10);
  const palette =
    live === "live"
      ? "border-emerald-500/40 bg-emerald-700/20 text-emerald-200"
      : "border-sky-500/40 bg-sky-700/20 text-sky-200";
  return (
    <span
      className={`rounded-full border px-2 py-0.5 text-[10px] font-semibold ${palette}`}
      title={live === "live" ? "Live (recent data)" : "Latest observation date"}
    >
      {dateLabel}
    </span>
  );
}

function isLive(source: SourceMetadata, recent: RecentRowsResult | null): "live" | "stale" | "unknown" {
  const latestDate = recent?.latestDate ?? deriveCardEnd(source);
  if (!latestDate) return "unknown";
  if (latestDate === "present") return "live";
  const parsed = Date.parse(latestDate);
  if (Number.isNaN(parsed)) return "unknown";
  const ageDays = (Date.now() - parsed) / (24 * 60 * 60 * 1000);
  return ageDays <= STALE_THRESHOLD_DAYS ? "live" : "stale";
}

function deriveCardEnd(source: SourceMetadata): string | null {
  const coverage = source.computed?.time_coverage;
  if (!coverage || coverage.length === 0) return null;
  return coverage[coverage.length - 1]?.end ?? null;
}

function Tag({ children }: { children: React.ReactNode }) {
  return (
    <span className="rounded-full border border-white/10 bg-white/[0.05] px-2 py-0.5 text-[10px] text-neutral-200">
      {children}
    </span>
  );
}

function formatCell(value: unknown): string {
  if (value === null || value === undefined) return "—";
  if (typeof value === "number") return Number.isFinite(value) ? value.toLocaleString() : String(value);
  return String(value);
}
