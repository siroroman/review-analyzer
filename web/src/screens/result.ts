import type { Metrics } from "../api/client";

export type Source = Metrics["trend"][number]["source"];
export type Summary = NonNull<Metrics["overall"]>;
type NonNull<T> = Exclude<T, null | undefined>;

export const SOURCE_LABEL: Record<Source, string> = { google_maps: "Google Maps", firmy_cz: "Firmy.cz" };

/** One decimal with a Czech comma, e.g. `4,4`. */
export function formatRating(value: number): string {
  return value.toLocaleString("cs-CZ", { minimumFractionDigits: 1, maximumFractionDigits: 1 });
}

/** Czech plural of "recenze": 1-4 recenze, otherwise recenzí. */
export function formatCount(count: number): string {
  const word = count >= 1 && count <= 4 ? "recenze" : "recenzí";
  return `${count} ${word}`;
}

const monthIndex = (date: string) => Number(date.slice(0, 4)) * 12 + Number(date.slice(5, 7)) - 1;

function weightedAverage(points: Metrics["trend"]): number | null {
  const total = points.reduce((sum, point) => sum + point.count, 0);
  if (total === 0) return null;
  return points.reduce((sum, point) => sum + point.average_rating * point.count, 0) / total;
}

/**
 * The rating of the last 12 months of the trend minus the 12 months before, weighted by Review count.
 * "Last" is counted from the newest trend month, so the answer depends on the data only.
 * Null when either window has no Reviews.
 */
export function changeAgainstPreviousYear(trend: Metrics["trend"]): number | null {
  if (trend.length === 0) return null;
  const newest = Math.max(...trend.map((point) => monthIndex(point.period_start)));
  const last = trend.filter((point) => monthIndex(point.period_start) > newest - 12);
  const before = trend.filter((point) => monthIndex(point.period_start) <= newest - 12 && monthIndex(point.period_start) > newest - 24);
  const now = weightedAverage(last);
  const then = weightedAverage(before);
  return now === null || then === null ? null : now - then;
}

export function formatChange(change: number): string {
  const rounded = Math.round(change * 10) / 10;
  if (rounded === 0) return "beze změny oproti předchozím 12 měsícům";
  return `${rounded > 0 ? "+" : "−"}${formatRating(Math.abs(rounded))} oproti předchozím 12 měsícům`;
}
