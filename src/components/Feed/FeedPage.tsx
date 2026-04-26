import { useEffect, useMemo, useRef, useState } from "react";
import { ArrowUpRight, Check, ChevronDown, ChevronRight, ExternalLink, Plus, RefreshCw, Search } from "lucide-react";
import { useDashboard } from "../../state/DashboardContext";
import { useRecentRows } from "../../data/hf/hooks";
import type { RecentRowsResult } from "../../data/hf/rows";
import type { SourceMetadata } from "../../types/source";

const STALE_THRESHOLD_DAYS = 90;

export function FeedPage() {
  const { catalog, refreshCatalog, scrollTargetId, setScrollTarget } = useDashboard();
  const [query, setQuery] = useState("");

  const visibleSources = useMemo(() => {
    if (!catalog.data) return [];
    if (!query) return catalog.data;
    const q = query.toLowerCase();
    return catalog.data.filter((s) =>
      [s.pretty_name, s.id, s.description ?? "", s.notes_general ?? "", s.pathogens.join(" ")]
        .join(" ")
        .toLowerCase()
        .includes(q)
    );
  }, [catalog.data, query]);

  return (
    <div className="space-y-3">
      <header className="flex flex-wrap items-center gap-3 rounded-xl border border-white/10 bg-black/60 px-4 py-2.5">
        <div className="flex items-baseline gap-2">
          <h1 className="text-sm font-semibold text-white">EPI-Eval datasets</h1>
          <a
            href="https://huggingface.co/EPI-Eval"
            target="_blank"
            rel="noreferrer"
            className="text-xs text-neutral-400 hover:text-red-200"
          >
            huggingface.co/EPI-Eval
          </a>
          {catalog.data && <span className="text-xs text-neutral-500">· {catalog.data.length}</span>}
        </div>
        <div className="relative ml-auto min-w-[220px] flex-1 max-w-md">
          <Search className="pointer-events-none absolute left-3 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-neutral-500" />
          <input
            type="search"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Search by name, pathogen, geography…"
            className="w-full rounded-md border border-white/10 bg-white/[0.03] py-1.5 pl-8 pr-3 text-xs text-white placeholder:text-neutral-500 focus:border-red-500 focus:outline-none"
          />
        </div>
        <button
          type="button"
          onClick={refreshCatalog}
          className="flex items-center gap-1 rounded-md border border-white/15 px-2 py-1 text-xs text-neutral-200 hover:border-red-500 hover:text-red-200"
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

      {catalog.status === "ready" && visibleSources.length === 0 && (
        <div className="rounded-xl border border-white/10 bg-white/[0.03] p-4 text-sm text-neutral-300">
          No datasets match.
        </div>
      )}

      {catalog.status === "ready" && (
        <ul className="space-y-1.5">
          {visibleSources.map((s) => (
            <DatasetCard
              key={s.id}
              source={s}
              autoExpand={s.id === scrollTargetId}
              onAutoConsumed={() => setScrollTarget(null)}
            />
          ))}
        </ul>
      )}
    </div>
  );
}

interface CardProps {
  source: SourceMetadata;
  autoExpand: boolean;
  onAutoConsumed: () => void;
}

function DatasetCard({ source, autoExpand, onAutoConsumed }: CardProps) {
  const { selectedSourceIds, toggleSourceSelected, openExplorer } = useDashboard();
  const selected = selectedSourceIds.includes(source.id);
  const [expanded, setExpanded] = useState(false);
  const containerRef = useRef<HTMLLIElement | null>(null);

  const recent = useRecentRows(source.id, 4, source.computed?.row_count);

  useEffect(() => {
    if (autoExpand) {
      setExpanded(true);
      containerRef.current?.scrollIntoView({ behavior: "smooth", block: "start" });
      onAutoConsumed();
    }
  }, [autoExpand, onAutoConsumed]);

  const live = useMemo(() => isLive(source, recent.data), [source, recent.data]);

  // Compact metadata pills shown on the always-visible row.
  const metaPills: string[] = [];
  if (source.cadence) metaPills.push(source.cadence);
  if (source.surveillance_category !== "none") metaPills.push(source.surveillance_category);
  if (source.pathogens.length > 0) metaPills.push(source.pathogens.slice(0, 2).join("·"));
  if (source.geography_countries.length > 0) metaPills.push(source.geography_countries.slice(0, 2).join("·"));

  return (
    <li
      ref={containerRef}
      className={`rounded-lg border bg-white/[0.03] ${
        selected ? "border-red-500/40" : "border-white/10"
      }`}
    >
      <div className="flex flex-wrap items-center gap-x-3 gap-y-1 px-3 py-2">
        <button
          type="button"
          onClick={() => setExpanded((v) => !v)}
          aria-expanded={expanded}
          aria-label={expanded ? "Collapse" : "Expand"}
          className="rounded p-0.5 text-neutral-400 hover:bg-white/5 hover:text-white"
        >
          {expanded ? <ChevronDown className="h-3.5 w-3.5" /> : <ChevronRight className="h-3.5 w-3.5" />}
        </button>

        <LiveBadge live={live} latestDate={recent.data?.latestDate ?? null} />

        <h3 className="truncate text-sm font-semibold text-white" title={source.pretty_name}>
          {source.pretty_name}
        </h3>
        <span className="truncate font-mono text-[10px] text-neutral-500" title={source.id}>
          {source.id}
        </span>

        {metaPills.length > 0 && (
          <span className="hidden text-[11px] text-neutral-400 lg:inline">{metaPills.join(" · ")}</span>
        )}

        <div className="ml-auto flex items-center gap-1.5">
          {source.source_url && (
            <a
              href={source.source_url}
              target="_blank"
              rel="noreferrer"
              className="flex items-center gap-1 rounded-md border border-white/10 px-2 py-0.5 text-[11px] text-neutral-200 hover:border-red-500 hover:text-red-200"
              title="Open at Huggingface"
            >
              Source <ExternalLink className="h-3 w-3" />
            </a>
          )}
          <button
            type="button"
            onClick={() => toggleSourceSelected(source.id)}
            aria-pressed={selected}
            className={`flex items-center gap-1 rounded-md border px-2 py-0.5 text-[11px] font-semibold transition ${
              selected
                ? "border-red-500/60 bg-red-700/40 text-red-100 hover:bg-red-700/55"
                : "border-white/15 bg-white/[0.04] text-neutral-200 hover:border-red-500 hover:text-red-200"
            }`}
          >
            {selected ? (
              <>
                <Check className="h-3 w-3" /> Selected
              </>
            ) : (
              <>
                <Plus className="h-3 w-3" /> Add
              </>
            )}
          </button>
          <button
            type="button"
            onClick={() => openExplorer(source.id)}
            className="flex items-center gap-1 rounded-md border border-red-500/40 bg-red-700/30 px-2 py-0.5 text-[11px] font-semibold text-red-100 hover:border-red-500/60 hover:bg-red-700/45"
            title="Open in Explorer"
          >
            Open data <ArrowUpRight className="h-3 w-3" />
          </button>
        </div>
      </div>

      {expanded && (
        <div className="border-t border-white/10 px-4 py-3">
          {source.description && (
            <p className="text-xs leading-5 text-neutral-300">{source.description}</p>
          )}
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
      <div className="overflow-x-auto">
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
  if (live === "unknown") {
    return (
      <span className="rounded-full border border-white/15 bg-white/[0.04] px-2 py-0.5 text-[10px] text-neutral-400">
        no date
      </span>
    );
  }
  const dateLabel = latestDate ? ` · ${latestDate.slice(0, 10)}` : "";
  if (live === "live") {
    return (
      <span className="rounded-full border border-emerald-500/40 bg-emerald-700/20 px-2 py-0.5 text-[10px] font-semibold text-emerald-200">
        Live{dateLabel}
      </span>
    );
  }
  return (
    <span className="rounded-full border border-amber-500/40 bg-amber-700/15 px-2 py-0.5 text-[10px] font-semibold text-amber-200">
      Stale{dateLabel}
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
