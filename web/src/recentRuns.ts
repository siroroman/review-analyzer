/** Results opened in this browser, kept for as long as the API keeps a Run's result in its cache. */
const KEY = "recent-runs";
const MAX_AGE_MS = 24 * 3_600_000;
const MAX_RUNS = 5;

export type RecentRun = { run_id: string; name: string; at: number };

function isRecentRun(value: unknown): value is RecentRun {
  if (typeof value !== "object" || value === null) return false;
  const run = value as Record<string, unknown>;
  return typeof run.run_id === "string" && typeof run.name === "string" && typeof run.at === "number";
}

function load(): RecentRun[] {
  try {
    const parsed: unknown = JSON.parse(localStorage.getItem(KEY) ?? "[]");
    return Array.isArray(parsed) ? parsed.filter(isRecentRun) : [];
  } catch {
    return [];
  }
}

/** The Runs opened in the last 24 hours before `now` (epoch ms), newest first. */
export function readRecent(now: number = Date.now()): RecentRun[] {
  return load()
    .filter((run) => now - run.at < MAX_AGE_MS)
    .sort((a, b) => b.at - a.at);
}

/** Remember that the result of a Run was opened at `now`; storage that is unavailable is ignored. */
export function rememberRun(runId: string, name: string, now: number = Date.now()): void {
  const kept = readRecent(now).filter((run) => run.run_id !== runId);
  const next = [{ run_id: runId, name, at: now }, ...kept].slice(0, MAX_RUNS);
  try {
    localStorage.setItem(KEY, JSON.stringify(next));
  } catch {
    // Private window or blocked storage: the box just stays empty.
  }
}
