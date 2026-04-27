// Concurrency gate + retry/backoff for HF datasets-server fetches.
//
// HF rate-limits the IP hard (especially anonymous), so:
//   - Anonymous: 1 in-flight at a time. Slower for multi-pane sessions but
//     the only safe default without auth.
//   - Authenticated (VITE_HF_TOKEN): 3 in-flight. Auth quota is much higher
//     so we can fan out without burning it.
//
// Even with the in-flight gate, fast successive requests can still pattern-
// match as a burst (Cloudflare's WAF watches request rate, not just
// concurrency). MIN_SPACING_MS enforces a floor between request *starts* so
// we don't tail-slap the rate limiter. 75ms is enough to look human-paced
// without meaningfully slowing pagination of a single slice.
//
// Retry handles three transient failure modes that all surface differently:
//   - 429 (rate-limit) — explicit backoff signal. HTTP error.
//   - 5xx (502/503/504) — datasets-server is occasionally flaky. HTTP error.
//   - TypeError "Failed to fetch" — Cloudflare drops the connection at the
//     network layer (no HTTP status). This is what most "Failed to load"
//     errors actually are after a sustained burst.
// Up to 3 retries with exponential backoff (300ms, 900ms, 2700ms). Other
// HTTP errors (400/403/404) don't retry — those are real problems.
//
// Cache hits in rows.ts bypass the queue (they don't touch the network).
//
// Read VITE_HF_TOKEN directly here rather than importing `hasHfToken` from
// `./client` — client.ts imports withGate from us, and pulling hasHfToken
// back the other way creates a circular import that fails module init.

const HAS_TOKEN = Boolean((import.meta.env.VITE_HF_TOKEN as string | undefined)?.trim());

const MAX_INFLIGHT = HAS_TOKEN ? 3 : 1;
const MAX_RETRIES = 3;
const BASE_BACKOFF_MS = 300;
const MIN_SPACING_MS = 75;

let active = 0;
let lastStartTs = 0;
const waiters: Array<() => void> = [];

function release(): void {
  active--;
  const next = waiters.shift();
  if (next) {
    active++;
    next();
  }
}

const sleep = (ms: number) => new Promise<void>((r) => setTimeout(r, ms));

/** Pace request *starts* so we don't trip burst-detection on a fast loop. */
async function spaceStart(): Promise<void> {
  const now = Date.now();
  const elapsed = now - lastStartTs;
  if (elapsed < MIN_SPACING_MS) {
    await sleep(MIN_SPACING_MS - elapsed);
  }
  lastStartTs = Date.now();
}

export function isRetryableHfError(err: unknown): boolean {
  if (!(err instanceof Error)) return false;
  // 429 — surfaced by client.ts in the message text. Match across all
  // entry points (rows / list datasets / splits) since they all share the
  // "HF <kind> failed: <code>" format.
  if (/^HF [\w ]+ failed: 429\b/.test(err.message)) return true;
  // 5xx — transient datasets-server / api hiccups.
  if (/^HF [\w ]+ failed: 5\d\d\b/.test(err.message)) return true;
  // Bare network failure (Cloudflare connection drop / DNS / etc.).
  // The browser fetch primitive throws TypeError("Failed to fetch") in
  // these cases; treat as retryable.
  if (err.name === "TypeError" && /failed to fetch|networkerror/i.test(err.message)) {
    return true;
  }
  return false;
}

export async function withGate<T>(fn: () => Promise<T>): Promise<T> {
  if (active >= MAX_INFLIGHT) {
    await new Promise<void>((resolve) => waiters.push(resolve));
  } else {
    active++;
  }
  try {
    let lastErr: unknown = null;
    for (let attempt = 0; attempt <= MAX_RETRIES; attempt++) {
      try {
        await spaceStart();
        return await fn();
      } catch (err) {
        lastErr = err;
        if (!isRetryableHfError(err) || attempt === MAX_RETRIES) throw err;
        const delay = BASE_BACKOFF_MS * Math.pow(3, attempt);
        const reason =
          err instanceof Error && err.name === "TypeError"
            ? "network drop"
            : err instanceof Error && /^HF [\w ]+ failed: 5/.test(err.message)
              ? "5xx"
              : "429";
        console.info(
          `HF transient (${reason}): retrying in ${delay}ms (attempt ${attempt + 1}/${MAX_RETRIES})`
        );
        await sleep(delay);
      }
    }
    throw lastErr;
  } finally {
    release();
  }
}
