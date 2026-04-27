import { useCallback, useRef, useState } from "react";
import { UploadCloud, X } from "lucide-react";
import { buildUserDataset, parseCsvText } from "../../data/predictions/parser";
import { usePredictions } from "../../state/PredictionsContext";

interface Props {
  onUploaded?: (datasetId: string) => void;
}

// Compact upload pill that fits in the FeedPage header bar. Click opens
// a file picker; dragging a CSV onto the pill drops directly. Errors
// surface in an anchored popover beneath the pill.
export function UploadZone({ onUploaded }: Props) {
  const [dragOver, setDragOver] = useState(false);
  const [errors, setErrors] = useState<string[]>([]);
  const inputRef = useRef<HTMLInputElement | null>(null);
  const { addDataset } = usePredictions();

  const handleFile = useCallback(
    async (file: File) => {
      setErrors([]);
      const text = await file.text();
      const parsed = parseCsvText(text);
      if (parsed.parseErrors.length > 0) {
        setErrors(parsed.parseErrors);
        return;
      }
      const built = buildUserDataset(parsed, { filename: file.name });
      if (!built.ok) {
        setErrors(built.errors);
        return;
      }
      addDataset(built.dataset);
      onUploaded?.(built.dataset.id);
    },
    [addDataset, onUploaded]
  );

  const onDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();
      setDragOver(false);
      const file = e.dataTransfer.files?.[0];
      if (file) void handleFile(file);
    },
    [handleFile]
  );

  return (
    <div className="relative flex items-center gap-1.5">
      <button
        type="button"
        onDragOver={(e) => {
          e.preventDefault();
          setDragOver(true);
        }}
        onDragLeave={() => setDragOver(false)}
        onDrop={onDrop}
        onClick={() => inputRef.current?.click()}
        title="Drop a prediction CSV or click to upload"
        className={`flex items-center gap-1 rounded-md border px-2 py-1 text-xs transition ${
          errors.length > 0
            ? "border-red-500/50 text-red-200 hover:border-red-400"
            : dragOver
              ? "border-sky-500 bg-sky-500/10 text-sky-100"
              : "border-white/15 text-neutral-200 hover:border-sky-500 hover:text-sky-200"
        }`}
      >
        <UploadCloud className="h-3 w-3" />
        {dragOver ? "Drop CSV" : "Upload CSV"}
      </button>
      <a
        href="examples/sample-prediction.csv"
        download
        className="text-[10px] text-neutral-500 underline hover:text-sky-200"
        title="Download a sample prediction CSV"
      >
        sample
      </a>
      <input
        ref={inputRef}
        type="file"
        accept=".csv,text/csv"
        className="hidden"
        onChange={(e) => {
          const f = e.target.files?.[0];
          if (f) void handleFile(f);
          e.target.value = "";
        }}
      />
      {errors.length > 0 && (
        <div className="absolute right-0 top-full z-30 mt-1 w-[320px] rounded-md border border-red-500/40 bg-red-950/95 p-2 text-[11px] text-red-200 shadow-lg backdrop-blur">
          <div className="flex items-baseline justify-between">
            <span className="font-semibold text-red-100">Upload failed</span>
            <button
              type="button"
              onClick={() => setErrors([])}
              className="rounded p-0.5 text-red-300 hover:bg-white/10 hover:text-red-100"
              aria-label="Dismiss errors"
            >
              <X className="h-3 w-3" />
            </button>
          </div>
          <ul className="mt-1 space-y-0.5">
            {errors.map((err, i) => (
              <li key={i}>{err}</li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}
