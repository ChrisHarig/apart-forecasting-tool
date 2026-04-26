import { useMemo, useState } from "react";
import { ArrowDown, ArrowUp, ArrowUpDown } from "lucide-react";
import type { DatasetRow } from "../../data/hf/rows";

interface Props {
  rows: DatasetRow[];
  initialPageSize?: number;
}

type SortDir = "asc" | "desc";
interface SortState {
  column: string | null;
  direction: SortDir;
}

export function DataTable({ rows, initialPageSize = 100 }: Props) {
  const [pageSize, setPageSize] = useState(initialPageSize);
  const [sort, setSort] = useState<SortState>({ column: null, direction: "asc" });

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

  const sortedRows = useMemo(() => {
    if (!sort.column) return rows;
    const col = sort.column;
    const isNumeric = numericColumns.has(col);
    const dir = sort.direction === "asc" ? 1 : -1;
    return [...rows].sort((a, b) => {
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
  }, [rows, sort, numericColumns]);

  const visible = sortedRows.slice(0, pageSize);

  const onHeaderClick = (col: string) =>
    setSort((prev) =>
      prev.column !== col
        ? { column: col, direction: "asc" }
        : prev.direction === "asc"
        ? { column: col, direction: "desc" }
        : { column: null, direction: "asc" }
    );

  if (rows.length === 0) {
    return <div className="rounded-lg border border-white/10 bg-white/[0.03] p-4 text-sm text-neutral-300">No rows.</div>;
  }

  return (
    <div className="space-y-2">
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
          Showing {visible.length.toLocaleString()} of {rows.length.toLocaleString()} fetched rows
          {sort.column && ` · sorted by ${sort.column} ${sort.direction}`}
        </span>
        {rows.length > pageSize && (
          <button
            type="button"
            onClick={() => setPageSize((p) => Math.min(p + 100, rows.length))}
            className="rounded border border-white/15 px-2 py-0.5 text-neutral-200 hover:border-red-500 hover:text-red-200"
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
