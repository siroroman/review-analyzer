import type { Metrics } from "../api/client";

export type Source = Metrics["trend"][number]["source"];
export type Summary = NonNull<Metrics["overall"]>;
type NonNull<T> = Exclude<T, null | undefined>;

export const SOURCE_LABEL: Record<Source, string> = { google_maps: "Google Maps", firmy_cz: "Firmy.cz" };

/** The display name of a Topic from the result's `topics`; the key itself when the result has no name for it. */
export function topicName(topics: ReadonlyArray<{ key: string; name: string }>, key: string): string {
  return topics.find((topic) => topic.key === key)?.name ?? key;
}

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

const plural = (count: number, one: string, few: string, many: string) => (count === 1 ? one : count >= 2 && count <= 4 ? few : many);

/** Czech plural of "zmínka": 1 zmínka, 2-4 zmínky, otherwise zmínek. */
export function formatMentions(count: number): string {
  return `${count} ${plural(count, "zmínka", "zmínky", "zmínek")}`;
}

/** The number of Flagged Reviews, which the analysis left out. */
export function formatExcluded(count: number): string {
  return `${count} ${plural(count, "podezřelá recenze vyřazena", "podezřelé recenze vyřazeny", "podezřelých recenzí vyřazeno")}`;
}

export const SERVICE_LABEL: Record<string, string> = { apify: "Apify", models: "Modely", google_places: "Google Places" };

const MONTHS = ["Leden", "Únor", "Březen", "Duben", "Květen", "Červen", "Červenec", "Srpen", "Září", "Říjen", "Listopad", "Prosinec"];

/** The Czech name of the month of an ISO date, capitalised, e.g. `Březen`. */
export function monthName(date: string): string {
  return MONTHS[Number(date.slice(5, 7)) - 1] ?? date;
}

/** The y axis of the rating chart: the data padded by a quarter star, rounded out to half stars, within 1 to 5, at least a star tall. */
export function ratingAxis(trend: Metrics["trend"]): {
  domain: [number, number];
  ticks: number[];
} {
  const ratings = trend.map((point) => point.average_rating);
  let low = ratings.length ? Math.max(1, Math.floor((Math.min(...ratings) - 0.25) * 2) / 2) : 1;
  let high = ratings.length ? Math.min(5, Math.ceil((Math.max(...ratings) + 0.25) * 2) / 2) : 5;
  if (high - low < 1) [low, high] = high === 5 ? [4, 5] : [low, low + 1];
  const ticks: number[] = [];
  for (let value = low; value <= high; value += 0.5) ticks.push(value);
  return { domain: [low, high], ticks };
}
