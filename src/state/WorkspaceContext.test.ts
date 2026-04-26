// Smoke tests for the pure functions in WorkspaceContext. The provider
// itself we'll exercise via integration testing once UI is wired up — for
// now this protects the persistence shape and the pane constructors.

import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { makeBrowserPane, makeExplorerPane } from "./WorkspaceContext";

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

describe("Workspace pane constructors", () => {
  beforeEach(() => {
    vi.stubGlobal("window", { localStorage: new MemStorage() } as unknown as Window);
  });
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("makeBrowserPane produces a tagged browser pane with empty query by default", () => {
    const p = makeBrowserPane();
    expect(p.type).toBe("browser");
    expect(p.id).toMatch(/^pane-/);
    expect(p.query).toBe("");
  });

  it("makeBrowserPane respects an explicit query", () => {
    const p = makeBrowserPane({ query: "ili" });
    expect(p.query).toBe("ili");
  });

  it("makeExplorerPane carries the sourceId and starts on the graph tab", () => {
    const p = makeExplorerPane("EPI-Eval/cdc-ilinet");
    expect(p.type).toBe("explorer");
    expect(p.sourceId).toBe("EPI-Eval/cdc-ilinet");
    expect(p.tab).toBe("graph");
    expect(p.chart.metric).toBeNull();
    expect(p.map.metric).toBeNull();
    expect(p.showTable).toBe(true);
  });

  it("makeExplorerPane reuses the supplied id (so converting a browser pane in place keeps its id)", () => {
    const p = makeExplorerPane("EPI-Eval/x", { id: "pane-fixed" });
    expect(p.id).toBe("pane-fixed");
  });
});
