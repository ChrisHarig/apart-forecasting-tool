// Tiny localStorage TTL cache. The user's rule is "no need to refetch more than
// hourly", so 1h is the default. Falls back to a no-op when localStorage is
// unavailable (SSR, private mode quotas).

// v2 (2026-04-26): bumped to flush catalogs cached before the predictions
// companion repos were filtered out. Old `:v1:` entries in localStorage are
// orphaned and will simply expire under their own TTL.
const PREFIX = "epieval-cache:v2:";
const DEFAULT_TTL_MS = 60 * 60 * 1000;

interface Entry<T> {
  ts: number;
  ttlMs: number;
  data: T;
}

function safeStorage(): Storage | null {
  try {
    return typeof window === "undefined" ? null : window.localStorage;
  } catch {
    return null;
  }
}

export function readCache<T>(key: string): T | null {
  const storage = safeStorage();
  if (!storage) return null;
  const raw = storage.getItem(PREFIX + key);
  if (!raw) return null;
  try {
    const entry = JSON.parse(raw) as Entry<T>;
    if (Date.now() - entry.ts > entry.ttlMs) {
      storage.removeItem(PREFIX + key);
      return null;
    }
    return entry.data;
  } catch {
    storage.removeItem(PREFIX + key);
    return null;
  }
}

export function writeCache<T>(key: string, data: T, ttlMs = DEFAULT_TTL_MS): void {
  const storage = safeStorage();
  if (!storage) return;
  const entry: Entry<T> = { ts: Date.now(), ttlMs, data };
  try {
    storage.setItem(PREFIX + key, JSON.stringify(entry));
  } catch {
    // Quota exceeded; drop silently. Catalog/row payloads are best-effort.
  }
}

export function clearCache(): void {
  const storage = safeStorage();
  if (!storage) return;
  for (let i = storage.length - 1; i >= 0; i--) {
    const key = storage.key(i);
    if (key && key.startsWith(PREFIX)) storage.removeItem(key);
  }
}
