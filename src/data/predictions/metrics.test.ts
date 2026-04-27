import { describe, expect, it } from "vitest";
import {
  alignedPairs,
  meanAbsoluteError,
  meanAbsolutePercentageError,
  outerJoinByDate,
  rootMeanSquaredError,
  signedBias
} from "./metrics";

describe("outerJoinByDate", () => {
  it("aligns matching dates", () => {
    const predictions = {
      rows: [
        { date: "2024-01-01", value: 10 },
        { date: "2024-01-08", value: 12 }
      ],
      dateField: "date",
      valueField: "value"
    };
    const truth = {
      rows: [
        { date: "2024-01-01", val: 9 },
        { date: "2024-01-08", val: 14 }
      ],
      dateField: "date",
      valueField: "val"
    };
    expect(outerJoinByDate(predictions, truth)).toEqual([
      { date: "2024-01-01", predicted: 10, observed: 9 },
      { date: "2024-01-08", predicted: 12, observed: 14 }
    ]);
  });

  it("keeps prediction-only and truth-only dates as half-null entries", () => {
    const predictions = {
      rows: [{ date: "2024-02-01", value: 20 }],
      dateField: "date",
      valueField: "value"
    };
    const truth = {
      rows: [{ date: "2024-01-01", val: 9 }],
      dateField: "date",
      valueField: "val"
    };
    const joined = outerJoinByDate(predictions, truth);
    expect(joined).toHaveLength(2);
    expect(joined.find((p) => p.date === "2024-02-01")).toEqual({
      date: "2024-02-01",
      predicted: 20,
      observed: null
    });
    expect(joined.find((p) => p.date === "2024-01-01")).toEqual({
      date: "2024-01-01",
      predicted: null,
      observed: 9
    });
  });

  it("strips time-of-day from ISO timestamps", () => {
    const predictions = {
      rows: [{ date: "2024-01-01T12:00:00Z", value: 10 }],
      dateField: "date",
      valueField: "value"
    };
    const truth = {
      rows: [{ date: "2024-01-01", val: 9 }],
      dateField: "date",
      valueField: "val"
    };
    const joined = outerJoinByDate(predictions, truth);
    expect(joined).toEqual([{ date: "2024-01-01", predicted: 10, observed: 9 }]);
  });

  it("means values within the same date bucket", () => {
    const predictions = {
      rows: [
        { date: "2024-01-01", value: 10 },
        { date: "2024-01-01", value: 20 }
      ],
      dateField: "date",
      valueField: "value"
    };
    const truth = {
      rows: [{ date: "2024-01-01", val: 0 }],
      dateField: "date",
      valueField: "val"
    };
    expect(outerJoinByDate(predictions, truth)[0].predicted).toBe(15);
  });

  it("ignores non-numeric values", () => {
    const predictions = {
      rows: [{ date: "2024-01-01", value: "n/a" }],
      dateField: "date",
      valueField: "value"
    };
    const truth = {
      rows: [{ date: "2024-01-01", val: 9 }],
      dateField: "date",
      valueField: "val"
    };
    expect(outerJoinByDate(predictions, truth)[0].predicted).toBeNull();
  });
});

describe("alignedPairs", () => {
  it("drops half-null pairs", () => {
    const { predicted, observed } = alignedPairs([
      { date: "a", predicted: 1, observed: 2 },
      { date: "b", predicted: 3, observed: null },
      { date: "c", predicted: null, observed: 4 }
    ]);
    expect(predicted).toEqual([1]);
    expect(observed).toEqual([2]);
  });
});

describe("meanAbsoluteError", () => {
  it("computes mean of |p − o|", () => {
    expect(meanAbsoluteError([1, 2, 3], [1, 4, 5])).toBe((0 + 2 + 2) / 3);
  });

  it("zero error → 0", () => {
    expect(meanAbsoluteError([1, 2, 3], [1, 2, 3])).toBe(0);
  });

  it("returns null on empty input", () => {
    expect(meanAbsoluteError([], [])).toBeNull();
  });
});

describe("rootMeanSquaredError", () => {
  it("computes sqrt(mean of squared errors)", () => {
    // errors 0, 2, 2 → squared 0, 4, 4 → mean 8/3 → sqrt
    expect(rootMeanSquaredError([1, 2, 3], [1, 4, 5])).toBeCloseTo(Math.sqrt(8 / 3));
  });

  it("zero on perfect match", () => {
    expect(rootMeanSquaredError([1, 2, 3], [1, 2, 3])).toBe(0);
  });

  it("returns null on empty input", () => {
    expect(rootMeanSquaredError([], [])).toBeNull();
  });
});

describe("meanAbsolutePercentageError", () => {
  it("computes mean of |p − o| / |o|", () => {
    // [(|2-1|/1) + (|4-2|/2)] / 2 = (1 + 1) / 2 = 1
    expect(meanAbsolutePercentageError([2, 4], [1, 2])).toBe(1);
  });

  it("skips rows where observed is exactly 0", () => {
    expect(meanAbsolutePercentageError([2, 4], [0, 2])).toBe(1); // only the second pair counted
  });

  it("returns null when every observed is 0", () => {
    expect(meanAbsolutePercentageError([1, 2], [0, 0])).toBeNull();
  });

  it("returns null on empty input", () => {
    expect(meanAbsolutePercentageError([], [])).toBeNull();
  });
});

describe("signedBias", () => {
  it("preserves sign", () => {
    expect(signedBias([2, 2, 2], [1, 1, 1])).toBe(1);
    expect(signedBias([1, 1, 1], [2, 2, 2])).toBe(-1);
  });

  it("zero on perfect match", () => {
    expect(signedBias([1, 2, 3], [1, 2, 3])).toBe(0);
  });

  it("returns null on empty input", () => {
    expect(signedBias([], [])).toBeNull();
  });
});
