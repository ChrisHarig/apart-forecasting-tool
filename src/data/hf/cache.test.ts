import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { clearCache, readCache, writeCache } from "./cache";

class MemStorage {
  private data = new Map<string, string>();
  get length() {
    return this.data.size;
  }
  key(i: number) {
    return Array.from(this.data.keys())[i] ?? null;
  }
  getItem(k: string) {
    return this.data.get(k) ?? null;
  }
  setItem(k: string, v: string) {
    this.data.set(k, v);
  }
  removeItem(k: string) {
    this.data.delete(k);
  }
  clear() {
    this.data.clear();
  }
}

describe("cache", () => {
  beforeEach(() => {
    vi.stubGlobal("window", { localStorage: new MemStorage() } as unknown as Window);
  });
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("round-trips a value within TTL", () => {
    writeCache("k", { a: 1 }, 60_000);
    expect(readCache<{ a: number }>("k")).toEqual({ a: 1 });
  });

  it("evicts after TTL", () => {
    const now = Date.now();
    vi.spyOn(Date, "now").mockReturnValue(now);
    writeCache("k", { a: 1 }, 1_000);
    vi.spyOn(Date, "now").mockReturnValue(now + 2_000);
    expect(readCache<{ a: number }>("k")).toBeNull();
  });

  it("clears all entries", () => {
    writeCache("a", 1);
    writeCache("b", 2);
    clearCache();
    expect(readCache("a")).toBeNull();
    expect(readCache("b")).toBeNull();
  });
});
