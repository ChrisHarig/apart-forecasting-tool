import { useMemo, useState } from "react";
import { ArrowDown, ArrowUp, ArrowUpDown, Download, Search } from "lucide-react";
import type { DatasetRow } from "../../data/hf/rows";

interface Props {
  rows: DatasetRow[];
  initialPageSize?: number;
  /** Used for the download filename. Falls back to "dataset" if absent. */
  filenameStem?: string;
}

type SortDir = "asc" | "desc";
interface SortState {
  column: string | null;
  direction: SortDir;
}

export function DataTable({ rows, initialPageSize = 100, filenameStem }: Props) {
  const [pageSize, setPageSize] = useState(initialPageSize);
  const [sort, setSort] = useState<SortState>({ column: null, direction: "asc" });
  const [filter, setFilter] = useState("");

  const columns = useMemo(() => {
    const seen = new Set<string>();
    for (const r of rows.slice(0, 200)) for (const k of Object.keys(r)) seen.add(k);
    return Array.from(seen);
  }, [rows]);

  const numericColumns = useMemo(() => {
    const set = new Set<string>();
    if (rows.length === 0) return set;
    const sample = rows.slice(0, 50);
    for (const col of columns) {
      let hits = 0;
      let nonNull = 0;
      for (const r of sample) {
        const v = r[col];
        if (v === null || v === undefined || v === "") continue;
        nonNull++;
        if (typeof v === "number" || (typeof v === "string" && !Number.isNaN(Number(v)))) hits++;
      }
      if (nonNull > 0 && hits / nonNull > 0.8) set.add(col);
    }
    return set;
  }, [rows, columns]);

  // Filter is applied before sort + paging, so the "Showing N of M" line
  // reflects what the user is actually looking at.
  const filteredRows = useMemo(() => {
    if (!filter.trim()) return rows;
    const needle = filter.toLowerCase();
    return rows.filter((r) => {
      for (const c of columns) {
        const v = r[c];
        if (v === null || v === undefined) continue;
        if (String(v).toLowerCase().includes(needle)) return true;
      }
      return false;
    });
  }, [rows, columns, filter]);

  const sortedRows = useMemo(() => {
    if (!sort.column) return filteredRows;
    const col = sort.column;
    const isNumeric = numericColumns.has(col);
    const dir = sort.direction === "asc" ? 1 : -1;
    return [...filteredRows].sort((a, b) => {
      const av = a[col];
      const bv = b[col];
      const aMissing = av === null || av === undefined || av === "";
      const bMissing = bv === null || bv === undefined || bv === "";
      if (aMissing && bMissing) return 0;
      if (aMissing) return 1; // nulls last
      if (bMissing) return -1;
      let cmp: number;
      if (isNumeric) cmp = Number(av) - Number(bv);
      else cmp = String(av).localeCompare(String(bv));
      return cmp * dir;
    });
  }, [filteredRows, sort, numericColumns]);

  const visible = sortedRows.slice(0, pageSize);

  const onHeaderClick = (col: string) =>
    setSort((prev) =>
      prev.column !== col
        ? { column: col, direction: "asc" }
        : prev.direction === "asc"
        ? { column: col, direction: "desc" }
        : { column: null, direction: "asc" }
    );

  // Download exports the *currently filtered + sorted* set, not just visible rows.
  // The filter/sort the user has set is "what they want"; the page-size limit
  // is a UI nicety, not a download intent.
  const stem = (filenameStem || "dataset").replace(/[^A-Za-z0-9-_.]/g, "-");
  const downloadCsv = () => {
    const blob = new Blob([toCsv(sortedRows, columns)], { type: "text/csv;charset=utf-8;" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `${stem}.csv`;
    document.body.appendChild(a);
    a.click();
    a.remove();
    URL.revokeObjectURL(url);
  };

  if (rows.length === 0) {
    return <div className="rounded-lg border border-white/10 bg-white/[0.03] p-4 text-sm text-neutral-300">No rows.</div>;
  }

  return (
    <div className="space-y-2">
      <div className="flex flex-wrap items-center gap-2">
        <div className="relative">
          <Search className="pointer-events-none absolute left-2 top-1/2 h-3 w-3 -translate-y-1/2 text-neutral-500" aria-hidden="true" />
          <input
            type="search"
            value={filter}
            onChange={(e) => setFilter(e.target.value)}
            placeholder="Filter rows…"
            className="w-48 rounded-md border border-white/10 bg-white/[0.03] py-1 pl-7 pr-2 text-xs text-white placeholder:text-neutral-500 focus:border-sky-500 focus:outline-none"
          />
        </div>
        <button
          type="button"
          onClick={downloadCsv}
          className="ml-auto flex items-center gap-1 rounded-md border border-white/15 px-2 py-1 text-xs text-neutral-200 transition hover:border-sky-500 hover:text-sky-200"
          title={
            filter
              ? `Download ${filteredRows.length.toLocaleString()} filtered rows as CSV`
              : `Download all ${rows.length.toLocaleString()} rows as CSV`
          }
        >
          <Download className="h-3 w-3" />
          Download CSV
        </button>
      </div>

      <div className="overflow-hidden rounded-lg border border-white/10 bg-neutral-950 text-neutral-100">
        <div className="max-h-[420px] overflow-auto">
          <table className="w-full min-w-max text-left text-xs">
            <thead className="sticky top-0 bg-white/[0.04] text-[10px] uppercase text-neutral-400 backdrop-blur">
              <tr>
                {columns.map((c) => {
                  const active = sort.column === c;
                  const Icon = !active ? ArrowUpDown : sort.direction === "asc" ? ArrowUp : ArrowDown;
                  return (
                    <th key={c} className="border-b border-white/10 px-3 py-2 font-semibold">
                      <button
                        type="button"
                        onClick={() => onHeaderClick(c)}
                        className={`flex items-center gap-1 whitespace-nowrap text-left transition hover:text-white ${
                          active ? "text-white" : "text-neutral-400"
                        }`}
                      >
                        <span>{c}</span>
                        <Icon
                          className={`h-3 w-3 ${active ? "opacity-100" : "opacity-30"}`}
                          aria-hidden="true"
                        />
                      </button>
                    </th>
                  );
                })}
              </tr>
            </thead>
            <tbody className="divide-y divide-white/[0.06]">
              {visible.map((row, i) => (
                <tr key={i} className="hover:bg-white/[0.03]">
                  {columns.map((c) => (
                    <td key={c} className="whitespace-nowrap px-3 py-1.5 text-neutral-200">
                      {formatCell(row[c])}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
      <div className="flex items-center gap-3 text-xs text-neutral-400">
        <span>
          Showing {visible.length.toLocaleString()} of {filteredRows.length.toLocaleString()}
          {filter && ` filtered`} rows
          {!filter && rows.length !== filteredRows.length ? ` (of ${rows.length.toLocaleString()})` : ""}
          {sort.column && ` · sorted by ${sort.column} ${sort.direction}`}
        </span>
        {filteredRows.length > pageSize && (
          <button
            type="button"
            onClick={() => setPageSize((p) => Math.min(p + 100, filteredRows.length))}
            className="rounded border border-white/15 px-2 py-0.5 text-neutral-200 hover:border-sky-500 hover:text-sky-200"
          >
            Show 100 more
          </button>
        )}
      </div>
    </div>
  );
}

function formatCell(value: unknown): string {
  if (value === null || value === undefined) return "—";
  if (typeof value === "number") return Number.isFinite(value) ? value.toLocaleString() : String(value);
  return String(value);
}

// RFC 4180 CSV: quote any field containing comma, quote, or newline; double
// embedded quotes. Booleans and null serialise predictably.
function toCsv(rows: DatasetRow[], columns: string[]): string {
  const lines: string[] = [columns.map(csvCell).join(",")];
  for (const row of rows) {
    lines.push(columns.map((c) => csvCell(row[c])).join(","));
  }
  return lines.join("\n");
}

function csvCell(value: unknown): string {
  if (value === null || value === undefined) return "";
  const s = typeof value === "number" || typeof value === "boolean" ? String(value) : String(value);
  if (/[",\n\r]/.test(s)) return `"${s.replace(/"/g, '""')}"`;
  return s;
}
