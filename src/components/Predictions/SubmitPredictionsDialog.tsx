import { useEffect, useMemo, useState } from "react";
import { CheckCircle2, ExternalLink, Loader2, X } from "lucide-react";
import { submitPredictionPr, siblingRepoId } from "../../data/predictions/hf-submit";
import {
  HF_SIGNUP_URL,
  HF_TOKEN_URL,
  clearStoredHfToken,
  getStoredHfToken,
  setStoredHfToken
} from "../../data/predictions/hf-token";
import type { UserDataset } from "../../data/predictions/types";

interface Props {
  dataset: UserDataset;
  targetDatasetId: string;
  targetColumn: string;
  passthroughDims: string[];
  onClose: () => void;
}

type Phase =
  | { kind: "form" }
  | { kind: "submitting" }
  | { kind: "success"; url: string; rowCount: number; repoId: string }
  | { kind: "error"; message: string };

export function SubmitPredictionsDialog({
  dataset,
  targetDatasetId,
  targetColumn,
  passthroughDims,
  onClose
}: Props) {
  const [submitter, setSubmitter] = useState("");
  const [modelName, setModelName] = useState("");
  const [description, setDescription] = useState("");
  const [token, setToken] = useState("");
  const [storedToken, setStoredToken] = useState<string | null>(() => getStoredHfToken());
  const [phase, setPhase] = useState<Phase>({ kind: "form" });

  // Esc to close (unless in flight).
  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      if (e.key === "Escape" && phase.kind !== "submitting") onClose();
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [phase.kind, onClose]);

  const repoId = useMemo(() => siblingRepoId(targetDatasetId), [targetDatasetId]);
  const formValid =
    submitter.trim().length > 0 &&
    modelName.trim().length > 0 &&
    description.trim().length >= 10 &&
    (storedToken !== null || token.trim().length > 0);

  async function handleSubmit() {
    const effectiveToken = storedToken ?? token.trim();
    if (!effectiveToken) return;
    if (!storedToken && token.trim()) {
      setStoredHfToken(token.trim());
      setStoredToken(token.trim());
    }
    setPhase({ kind: "submitting" });
    try {
      const result = await submitPredictionPr({
        dataset,
        accessToken: effectiveToken,
        meta: {
          submitter: submitter.trim(),
          modelName: modelName.trim(),
          description: description.trim(),
          targetDataset: targetDatasetId,
          targetColumn,
          passthroughDims
        }
      });
      setPhase({
        kind: "success",
        url: result.pullRequestUrl,
        rowCount: result.rowCount,
        repoId: result.repoId
      });
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err);
      setPhase({ kind: "error", message: humanizeError(msg, repoId) });
    }
  }

  function handleClearToken() {
    clearStoredHfToken();
    setStoredToken(null);
    setToken("");
  }

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-sm"
      onClick={() => phase.kind !== "submitting" && onClose()}
    >
      <div
        className="w-[520px] max-w-[92vw] rounded-lg border border-white/10 bg-neutral-950 p-5 shadow-2xl"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="mb-4 flex items-start justify-between gap-3">
          <div>
            <h2 className="text-base font-semibold text-white">
              Submit predictions to HuggingFace
            </h2>
            <p className="mt-0.5 text-[11px] text-neutral-400">
              Opens a community pull request on{" "}
              <span className="font-mono text-neutral-300">{repoId}</span>. A
              maintainer reviews and merges before predictions become public.
            </p>
          </div>
          <button
            type="button"
            onClick={onClose}
            disabled={phase.kind === "submitting"}
            className="rounded p-1 text-neutral-400 hover:bg-white/10 hover:text-white disabled:opacity-30"
            aria-label="Close"
          >
            <X className="h-4 w-4" />
          </button>
        </div>

        {phase.kind === "success" ? (
          <SuccessPanel
            url={phase.url}
            rowCount={phase.rowCount}
            repoId={phase.repoId}
            onClose={onClose}
          />
        ) : (
          <form
            className="space-y-3"
            onSubmit={(e) => {
              e.preventDefault();
              if (formValid && phase.kind !== "submitting") void handleSubmit();
            }}
          >
            <Field label="Submitter" hint="Your name or HF username">
              <input
                type="text"
                value={submitter}
                onChange={(e) => setSubmitter(e.target.value)}
                disabled={phase.kind === "submitting"}
                required
                className="w-full rounded-md border border-white/10 bg-black/60 px-2 py-1.5 text-sm text-white placeholder-neutral-500 focus:border-sky-500 focus:outline-none"
                placeholder="alice"
              />
            </Field>
            <Field label="Model name" hint="Identifier for this model run">
              <input
                type="text"
                value={modelName}
                onChange={(e) => setModelName(e.target.value)}
                disabled={phase.kind === "submitting"}
                required
                className="w-full rounded-md border border-white/10 bg-black/60 px-2 py-1.5 text-sm text-white placeholder-neutral-500 focus:border-sky-500 focus:outline-none"
                placeholder="my-flu-arima v0.3"
              />
            </Field>
            <Field
              label="Description"
              hint="Brief notes for the reviewer (≥ 10 chars)"
            >
              <textarea
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                disabled={phase.kind === "submitting"}
                required
                minLength={10}
                rows={3}
                className="w-full resize-none rounded-md border border-white/10 bg-black/60 px-2 py-1.5 text-sm text-white placeholder-neutral-500 focus:border-sky-500 focus:outline-none"
                placeholder="Approach, training data, known caveats…"
              />
            </Field>

            <TokenField
              storedToken={storedToken}
              token={token}
              onChangeToken={setToken}
              onClear={handleClearToken}
              disabled={phase.kind === "submitting"}
            />

            <div className="rounded-md border border-white/10 bg-white/[0.02] px-2.5 py-2 text-[11px] text-neutral-400">
              <p>
                Will commit a parquet under{" "}
                <span className="font-mono text-neutral-300">data/&lt;name&gt;-&lt;ts&gt;.parquet</span>{" "}
                with {dataset.rowCount.toLocaleString()} long-format rows for{" "}
                <span className="font-mono text-neutral-300">{targetColumn}</span>.
              </p>
            </div>

            {phase.kind === "error" && (
              <div className="rounded-md border border-red-500/40 bg-red-950/40 px-3 py-2 text-xs text-red-200">
                {phase.message}
              </div>
            )}

            <div className="flex items-center justify-end gap-2 pt-1">
              <button
                type="button"
                onClick={onClose}
                disabled={phase.kind === "submitting"}
                className="rounded-md border border-white/10 px-3 py-1.5 text-xs text-neutral-200 hover:border-white/20 hover:text-white disabled:opacity-40"
              >
                Cancel
              </button>
              <button
                type="submit"
                disabled={!formValid || phase.kind === "submitting"}
                className="flex items-center gap-1.5 rounded-md border border-sky-500/60 bg-sky-700/40 px-3 py-1.5 text-xs font-semibold text-sky-50 hover:border-sky-400 hover:bg-sky-700/60 disabled:cursor-not-allowed disabled:opacity-40"
              >
                {phase.kind === "submitting" && <Loader2 className="h-3 w-3 animate-spin" />}
                {phase.kind === "submitting" ? "Submitting…" : "Open PR on HuggingFace"}
              </button>
            </div>
          </form>
        )}
      </div>
    </div>
  );
}

interface FieldProps {
  label: string;
  hint?: React.ReactNode;
  children: React.ReactNode;
}

function Field({ label, hint, children }: FieldProps) {
  return (
    <label className="block">
      <div className="mb-1 flex items-baseline justify-between">
        <span className="text-[10px] font-semibold uppercase text-neutral-400">{label}</span>
        {hint && <span className="text-[10px] text-neutral-500">{hint}</span>}
      </div>
      {children}
    </label>
  );
}

interface TokenFieldProps {
  storedToken: string | null;
  token: string;
  onChangeToken: (v: string) => void;
  onClear: () => void;
  disabled: boolean;
}

function TokenField({ storedToken, token, onChangeToken, onClear, disabled }: TokenFieldProps) {
  if (storedToken) {
    return (
      <div className="rounded-md border border-emerald-500/30 bg-emerald-500/[0.05] px-2.5 py-2 text-[11px] text-emerald-100">
        <div className="flex items-center justify-between gap-2">
          <span>HuggingFace token stored locally ({maskToken(storedToken)}).</span>
          <button
            type="button"
            onClick={onClear}
            disabled={disabled}
            className="text-[11px] text-emerald-300 underline hover:text-emerald-200 disabled:opacity-50"
          >
            Change
          </button>
        </div>
      </div>
    );
  }
  return (
    <Field
      label="Your HuggingFace token"
      hint={
        <span className="text-neutral-500">paste below</span>
      }
    >
      <input
        type="password"
        value={token}
        onChange={(e) => onChangeToken(e.target.value)}
        disabled={disabled}
        required
        autoComplete="off"
        className="w-full rounded-md border border-white/10 bg-black/60 px-2 py-1.5 font-mono text-xs text-white placeholder-neutral-500 focus:border-sky-500 focus:outline-none"
        placeholder="hf_…"
      />
      <ol className="mt-1.5 space-y-0.5 text-[10px] text-neutral-400">
        <li>
          1. No HF account?{" "}
          <a
            href={HF_SIGNUP_URL}
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex items-center gap-0.5 text-sky-300 hover:text-sky-200"
          >
            sign up free <ExternalLink className="h-2.5 w-2.5" />
          </a>
          .
        </li>
        <li>
          2. Create a personal{" "}
          <a
            href={HF_TOKEN_URL}
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex items-center gap-0.5 text-sky-300 hover:text-sky-200"
          >
            Write-scoped token <ExternalLink className="h-2.5 w-2.5" />
          </a>{" "}
          and paste it above.
        </li>
        <li className="text-neutral-500">
          The token authenticates as <em>you</em>, not the maintainer — your PR
          arrives with your HF username on it. Stored only in this browser's
          localStorage.
        </li>
      </ol>
    </Field>
  );
}

interface SuccessPanelProps {
  url: string;
  rowCount: number;
  repoId: string;
  onClose: () => void;
}

function SuccessPanel({ url, rowCount, repoId, onClose }: SuccessPanelProps) {
  return (
    <div className="space-y-3">
      <div className="flex items-start gap-2 rounded-md border border-emerald-500/40 bg-emerald-500/[0.06] px-3 py-2 text-xs text-emerald-100">
        <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0" />
        <div>
          <p className="font-semibold text-emerald-50">Pull request opened.</p>
          <p className="mt-0.5 text-[11px] text-emerald-200/90">
            {rowCount.toLocaleString()} rows uploaded to{" "}
            <span className="font-mono">{repoId}</span>. A maintainer will review
            on HuggingFace and merge to publish.
          </p>
        </div>
      </div>
      <a
        href={url}
        target="_blank"
        rel="noopener noreferrer"
        className="flex items-center justify-center gap-1.5 rounded-md border border-sky-500/60 bg-sky-700/40 px-3 py-2 text-sm font-semibold text-sky-50 hover:border-sky-400 hover:bg-sky-700/60"
      >
        View pull request
        <ExternalLink className="h-3.5 w-3.5" />
      </a>
      <div className="flex justify-end">
        <button
          type="button"
          onClick={onClose}
          className="rounded-md border border-white/10 px-3 py-1.5 text-xs text-neutral-200 hover:border-white/20 hover:text-white"
        >
          Close
        </button>
      </div>
    </div>
  );
}

function maskToken(t: string): string {
  if (t.length <= 8) return "••••";
  return `${t.slice(0, 3)}…${t.slice(-4)}`;
}

function humanizeError(msg: string, repoId: string): string {
  if (/401|invalid.*token|unauthorized/i.test(msg)) {
    return "Authentication failed. Double-check that your token has write scope.";
  }
  if (/404|not found/i.test(msg)) {
    return `The dataset ${repoId} doesn't exist on HuggingFace yet. A maintainer needs to create it before predictions can be submitted.`;
  }
  if (/403|forbidden/i.test(msg)) {
    return "HuggingFace rejected the PR (403). Token may lack write scope, or the repo may be locked.";
  }
  return msg;
}
