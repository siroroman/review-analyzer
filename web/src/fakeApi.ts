import { vi } from "vitest";
import type { Api } from "./api/client";

/** An `Api` whose every call is a spy returning something harmless; a test overrides what it cares about. */
export function fakeApi(overrides: Partial<Api> = {}): { [K in keyof Api]: ReturnType<typeof vi.fn<Api[K]>> } {
  return {
    suggest: vi.fn(async () => []),
    branches: vi.fn(async () => []),
    startRun: vi.fn(async () => ({ run_id: "run-1", status: "queued" as const, reused: false })),
    runProgress: vi.fn(async () => ({ run_id: "run-1", status: "queued" as const, finished: false, cost: "0" })),
    ...overrides,
  } as never;
}
