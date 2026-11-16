import { readRecent, rememberRun } from "./recentRuns";

const HOUR = 3_600_000;

beforeEach(() => localStorage.clear());
afterEach(() => vi.restoreAllMocks());

describe("recent Runs", () => {
  it("is empty when nothing was opened", () => {
    expect(readRecent(0)).toEqual([]);
  });

  it("returns the newest Run first", () => {
    rememberRun("a", "Alza", 1 * HOUR);
    rememberRun("b", "Rohlik", 2 * HOUR);
    expect(readRecent(3 * HOUR).map((run) => run.run_id)).toEqual(["b", "a"]);
  });

  it("forgets what was opened more than 24 hours ago", () => {
    rememberRun("old", "Stará", 0);
    rememberRun("new", "Nová", 25 * HOUR);
    expect(readRecent(25 * HOUR).map((run) => run.run_id)).toEqual(["new"]);
  });

  it("keeps a Run once and moves it to the front when opened again", () => {
    rememberRun("a", "Alza", 1 * HOUR);
    rememberRun("b", "Rohlik", 2 * HOUR);
    rememberRun("a", "Alza", 3 * HOUR);
    expect(readRecent(4 * HOUR).map((run) => run.run_id)).toEqual(["a", "b"]);
  });

  it("keeps at most five Runs", () => {
    for (let i = 0; i < 7; i++) rememberRun(`r${i}`, `Firma ${i}`, i * 1000);
    expect(readRecent(10_000).map((run) => run.run_id)).toEqual(["r6", "r5", "r4", "r3", "r2"]);
  });

  it("ignores damaged stored data", () => {
    localStorage.setItem("recent-runs", "{not json");
    expect(readRecent(0)).toEqual([]);
    localStorage.setItem("recent-runs", JSON.stringify([{ run_id: 1 }, "x", null]));
    expect(readRecent(0)).toEqual([]);
  });

  it("does not throw when the storage is unavailable", () => {
    vi.spyOn(Storage.prototype, "getItem").mockImplementation(() => {
      throw new DOMException("blocked", "SecurityError");
    });
    vi.spyOn(Storage.prototype, "setItem").mockImplementation(() => {
      throw new DOMException("full", "QuotaExceededError");
    });
    expect(() => rememberRun("a", "Alza", 0)).not.toThrow();
    expect(readRecent(0)).toEqual([]);
  });
});
