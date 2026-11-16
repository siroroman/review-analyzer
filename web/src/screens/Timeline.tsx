import { CartesianGrid, Line, LineChart, ReferenceArea, ReferenceDot, ResponsiveContainer, XAxis, YAxis } from "recharts";
import type { Metrics } from "../api/client";
import { SOURCE_LABEL, formatRating, topicName, type Source } from "./result";

/** Line style tells the Sources apart as well as the hue: solid for Google Maps, dashed for Firmy.cz. */
const LINES: Record<Source, { color: string; dash: string | undefined }> = {
  google_maps: { color: "#2457C5", dash: undefined },
  firmy_cz: { color: "#B85A00", dash: "6 4" },
};
const DROP = "#B3261E";
const RISE = "#1E7B45";

export const monthLabel = (date: string) => `${date.slice(5, 7)}/${date.slice(0, 4)}`;

/** What the chart says, in words: the first and last rating and the range per Source. */
function describe(trend: Metrics["trend"]): string {
  const parts = (Object.keys(LINES) as Source[]).flatMap((source) => {
    const points = trend.filter((point) => point.source === source).sort((a, b) => a.period_start.localeCompare(b.period_start));
    if (points.length === 0) return [];
    const first = points[0]!;
    const last = points[points.length - 1]!;
    const ratings = points.map((point) => point.average_rating);
    return [
      `${SOURCE_LABEL[source]}: od ${formatRating(first.average_rating)} (${monthLabel(first.period_start)}) do ${formatRating(last.average_rating)} (${monthLabel(last.period_start)}), nejnižší ${formatRating(Math.min(...ratings))}, nejvyšší ${formatRating(Math.max(...ratings))}.`,
    ];
  });
  return `Vývoj hodnocení po měsících. ${parts.join(" ")}`;
}

const signed = (delta: number) => `${delta < 0 ? "−" : "+"}${formatRating(Math.abs(delta))}`;

/** Rating per month for each Source, with the drop and rise months marked and listed. */
export function Timeline({
  trend,
  changes,
  topics,
}: {
  trend: Metrics["trend"];
  changes: Metrics["changes"];
  topics: ReadonlyArray<{ key: string; name: string }>;
}) {
  const months = [...new Set(trend.map((point) => point.period_start))].sort();
  const rows = months.map((month) => ({
    month,
    ...Object.fromEntries(trend.filter((point) => point.period_start === month).map((point) => [point.source, point.average_rating])),
  }));
  const sources = (Object.keys(LINES) as Source[]).filter((source) => trend.some((point) => point.source === source));
  const ratingAt = (source: Source, month: string) => trend.find((point) => point.source === source && point.period_start === month)?.average_rating;

  return (
    <div>
      <div role="img" aria-label={describe(trend)} className="h-72 rounded-card border border-line bg-card p-2">
        <ResponsiveContainer width="100%" height="100%" initialDimension={{ width: 640, height: 280 }}>
          <LineChart data={rows} margin={{ top: 24, right: 16, bottom: 4, left: 0 }}>
            <CartesianGrid stroke="#E3E2DC" vertical={false} />
            <XAxis dataKey="month" scale="band" tickFormatter={monthLabel} stroke="#5B616A" />
            <YAxis domain={[1, 5]} ticks={[1, 2, 3, 4, 5]} stroke="#5B616A" width={28} />
            {changes
              .filter((change) => change.kind === "drop")
              .map((change) => (
                <ReferenceArea key={`area-${change.source}-${change.period_start}`} x1={change.period_start} x2={change.period_start} fill={DROP} fillOpacity={0.12} />
              ))}
            {sources.map((source) => (
              <Line key={source} dataKey={source} name={SOURCE_LABEL[source]} stroke={LINES[source].color} strokeDasharray={LINES[source].dash} strokeWidth={2} connectNulls isAnimationActive={false} />
            ))}
            {changes.map((change) => {
              const y = ratingAt(change.source, change.period_start);
              if (y === undefined) return null;
              const drop = change.kind === "drop";
              return (
                <ReferenceDot
                  key={`dot-${change.kind}-${change.source}-${change.period_start}`}
                  x={change.period_start}
                  y={y}
                  r={6}
                  fill={drop ? DROP : RISE}
                  stroke="#fff"
                  label={{ value: drop ? `pokles${change.main_topic_key ? ` + ${topicName(topics, change.main_topic_key)}` : ""}` : "vzestup", position: "top", fill: drop ? DROP : RISE, fontSize: 12 }}
                />
              );
            })}
          </LineChart>
        </ResponsiveContainer>
      </div>
      {changes.length > 0 && (
        <ul aria-label="Poklesy a vzestupy" className="mt-3 space-y-1 text-sm">
          {changes.map((change) => (
            <li key={`${change.kind}-${change.source}-${change.period_start}`}>
              {change.kind === "drop" ? "Pokles" : "Vzestup"} · {SOURCE_LABEL[change.source]} · {monthLabel(change.period_start)}: {signed(change.delta)}
              {change.main_topic_key ? ` · hlavní téma: ${topicName(topics, change.main_topic_key)}` : ""}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
