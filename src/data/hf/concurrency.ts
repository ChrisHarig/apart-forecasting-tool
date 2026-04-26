// Concurrency gate + 429 auto-retry for HF datasets-server fetches.
//
// HF rate-limits the IP hard (especially anonymous), so:
//   - Anonymous: 1 in-flight at a time. Slower for multi-pane sessions but
//     the only safe default without auth.
//   - Authenticated (VITE_HF_TOKEN): 3 in-flight. Auth quota is much higher
//     so we can fan out without burning it.
//
// Auto-retry handles the case where one page in the middle of a 50-page
// dataset slice hits a transient 429 — without it, a single rate-limit blip
// kills the whole pane's fetch. Up to 3 retries with exponential backoff
// (300ms, 900ms, 2700ms). Other HTTP errors don't retry — those are real
// problems and silent retry would mask them.
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

let active = 0;
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

/** A 429 from HF is signalled by the error message text we emit in client.ts. */
function is429(err: unknown): boolean {
  return err instanceof Error && /^HF rows failed: 429\b/.test(err.message);
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
        return await fn();
      } catch (err) {
        lastErr = err;
        if (!is429(err) || attempt === MAX_RETRIES) throw err;
        // Exponential backoff: 300 → 900 → 2700 ms. Honest in console so
        // the user can see the system is recovering, not stuck.
        const delay = BASE_BACKOFF_MS * Math.pow(3, attempt);
        console.info(`HF 429: retrying in ${delay}ms (attempt ${attempt + 1}/${MAX_RETRIES})`);
        await sleep(delay);
      }
    }
    throw lastErr;
  } finally {
    release();
  }
}
