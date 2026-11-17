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

const plural = (count: number, one: string, few: string, many: string) => (count === 1 ? one : count >= 2 && count <= 4 ? few : many);

/** Czech plural of "zmínka": 1 zmínka, 2-4 zmínky, otherwise zmínek. */
export function formatMentions(count: number): string {
  return `${count} ${plural(count, "zmínka", "zmínky", "zmínek")}`;
}

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
