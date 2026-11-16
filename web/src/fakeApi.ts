import { vi } from "vitest";
import type { Api, RunResult } from "./api/client";

/** An `Api` whose every call is a spy returning something harmless; a test overrides what it cares about. */
export function fakeApi(overrides: Partial<Api> = {}): { [K in keyof Api]: ReturnType<typeof vi.fn<Api[K]>> } {
  return {
    suggest: vi.fn(async () => []),
    branches: vi.fn(async () => []),
    startRun: vi.fn(async () => ({ run_id: "run-1", status: "queued" as const, reused: false })),
    runProgress: vi.fn(async () => ({
      run_id: "run-1",
      status: "queued" as const,
      finished: false,
      cost: "0",
      budget: "1",
      downloaded: null,
      flagged: null,
      classified: null,
      to_classify: null,
      step_cost: { downloading: null, classifying: null, analysis: null },
    })),
    runResult: vi.fn(async () => fakeResult()),
    reviews: vi.fn(async () => []),
    ...overrides,
  } as never;
}

/** A finished Run with one Place on Google Maps and a two-month trend; a test overrides what it cares about. */
export function fakeResult(overrides: Partial<RunResult> = {}): RunResult {
  return {
    run_id: "run-1",
    status: "done",
    company: { name: "Kavárna U Mlýna", industry: "cafe", places: [{ source: "google_maps", external_id: "g1", name: "Kavárna U Mlýna", address: "Praha" }] },
    metrics: {
      trend: [
        { source: "google_maps", period_start: "2026-01-01", average_rating: 4.5, count: 10, sentiment: 0.6 },
        { source: "google_maps", period_start: "2026-02-01", average_rating: 3.5, count: 8, sentiment: 0.1 },
      ],
      topic_shares: [],
      changes: [],
      overall: { average_rating: 4.0, count: 18 },
      per_source: [{ source: "google_maps", summary: { average_rating: 4.0, count: 18 } }],
      per_place: [{ source: "google_maps", place_external_id: "g1", summary: { average_rating: 4.0, count: 18 } }],
    },
    insights: [],
    topics: [],
    reviews: 18,
    flagged: 0,
    unclassified: 0,
    cost: "0.42",
    notes: [],
    ...overrides,
  };
}
