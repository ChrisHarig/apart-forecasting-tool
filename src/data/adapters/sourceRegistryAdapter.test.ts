import { afterEach, describe, expect, it } from "vitest";
import { sourceCatalog } from "../sources/sourceCatalog";
import {
  getSourcesForCountry,
  normalizeCoverageCountries,
  sourceRegistryAdapter,
  validateSourceInput
} from "./sourceRegistryAdapter";
import type { AddSourceInput } from "../../types/source";

function installMemoryStorage() {
  const values = new Map<string, string>();
  const localStorage = {
    get length() {
      return values.size;
    },
    clear: () => values.clear(),
    getItem: (key: string) => values.get(key) ?? null,
    key: (index: number) => [...values.keys()][index] ?? null,
    removeItem: (key: string) => {
      values.delete(key);
    },
    setItem: (key: string, value: string) => {
      values.set(key, value);
    }
  } satisfies Storage;

  Object.defineProperty(globalThis, "window", {
    configurable: true,
    value: { localStorage }
  });
}

const validSourceInput: AddSourceInput = {
  name: "Regional aggregate wastewater feed",
  url: "https://example.org/feed.csv",
  category: "user_added",
  countries: ["United States"],
  dataType: "Weekly aggregate sewershed index",
  updateCadence: "Weekly",
  notes: "Country-level aggregate summary for analyst testing."
};

afterEach(() => {
  Reflect.deleteProperty(globalThis, "window");
});

describe("source registry adapter", () => {
  it("filters sources by selected ISO3 while retaining global source candidates", () => {
    const usaSources = getSourcesForCountry(sourceCatalog, "USA").map((source) => source.id);
    const canadaSources = getSourcesForCountry(sourceCatalog, "CAN").map((source) => source.id);

    expect(usaSources).toContain("cdc-nwss");
    expect(usaSources).toContain("who-flunet");
    expect(canadaSources).toContain("who-flunet");
    expect(canadaSources).not.toContain("cdc-nwss");
  });

  it("normalizes country names and ISO aliases to stable ISO3 codes", () => {
    expect(normalizeCoverageCountries(["United States", "ca", "GLOBAL", "not-a-country"])).toEqual([
      "USA",
      "CAN",
      "GLOBAL"
    ]);
  });

  it("rejects source metadata that describes individual or medical-record content", () => {
    const validation = validateSourceInput({
      ...validSourceInput,
      notes: "Contains patient record extracts and individual device id fields."
    });

    expect(validation.valid).toBe(false);
    expect(validation.errors.join(" ")).toMatch(/aggregate data/i);
  });

  it("persists user-added sources and labels them as unvalidated", () => {
    installMemoryStorage();

    const result = sourceRegistryAdapter.addUserSource(validSourceInput);
    const saved = sourceRegistryAdapter.loadUserSources();

    expect(result.validation.valid).toBe(true);
    expect(saved).toHaveLength(1);
    expect(saved[0]).toMatchObject({
      name: "Regional aggregate wastewater feed",
      supportedCountries: ["USA"],
      userAdded: true,
      validationStatus: "not validated",
      privacyClassification: "aggregate restricted"
    });
  });
});
