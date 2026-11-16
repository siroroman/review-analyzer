import { CartesianGrid, Line, LineChart, ReferenceArea, ReferenceDot, ResponsiveContainer, XAxis, YAxis, usePlotArea } from "recharts";
import type { Metrics } from "../api/client";
import { SOURCE_LABEL, formatRating, monthName, ratingAxis, topicName, type Source } from "./result";

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

/** The marker of a drop or rise: a hollow dot in the colour of its Source and a callout beside it. */
function Marker({ cx, cy, color, lines, drop }: { cx?: number; cy?: number; color: string; lines: string[]; drop: boolean }) {
  const area = usePlotArea();
  if (cx === undefined || cy === undefined) return null;
  const width = Math.max(...lines.map((line) => line.length)) * 6.6 + 24;
  const height = lines.length === 1 ? 28 : 46;
  const left = area?.x ?? 0;
  const right = left + (area?.width ?? width);
  const wanted = drop ? (cx + 16 + width <= right ? cx + 16 : cx - 16 - width) : cx - width / 2;
  const x = Math.max(left, Math.min(wanted, right - width));
  const bottom = (area?.y ?? 0) + (area?.height ?? cy + height + 14);
  const y = drop ? (area?.y ?? 0) + 6 : Math.max(cy + 12, bottom - height - 4);
  return (
    <g>
      <line x1={cx} y1={drop ? y + height : cy + 6} x2={cx} y2={drop ? cy - 6 : y} stroke={drop ? DROP : RISE} strokeWidth={1} strokeDasharray="3 3" />
      <circle cx={cx} cy={cy} r={5} fill="#fff" stroke={color} strokeWidth={2.5} />
      <rect x={x} y={y} width={width} height={height} rx={8} fill={drop ? "#1B1F23" : "#DCE6FA"} />
      {lines.map((line, index) => (
        <text key={line} x={x + 12} y={y + 18 + index * 17} fontSize={12} fontWeight={index === 0 ? 700 : 400} fill={drop ? "#fff" : "#1B1F23"}>
          {line}
        </text>
      ))}
    </g>
  );
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
  const axis = ratingAxis(trend);
  const ratingAt = (source: Source, month: string) => trend.find((point) => point.source === source && point.period_start === month)?.average_rating;

  return (
    <div>
      <ul aria-label="Legenda grafu" className="mb-2 flex flex-wrap gap-x-4 gap-y-1 text-sm text-muted">
        {sources.map((source) => (
          <li key={source} className="flex items-center gap-1.5">
            <svg width="22" height="6" aria-hidden="true">
              <line x1="0" y1="3" x2="22" y2="3" stroke={LINES[source].color} strokeWidth="3" strokeDasharray={LINES[source].dash} />
            </svg>
            {SOURCE_LABEL[source]}
          </li>
        ))}
      </ul>
      <div role="img" aria-label={describe(trend)} className="h-72">
        <ResponsiveContainer width="100%" height="100%" initialDimension={{ width: 640, height: 280 }}>
          <LineChart data={rows} margin={{ top: 24, right: 16, bottom: 4, left: 0 }}>
            <CartesianGrid stroke="#E3E2DC" vertical={false} />
            <XAxis dataKey="month" scale="band" tickFormatter={monthLabel} stroke="#5B616A" />
            <YAxis domain={axis.domain} ticks={axis.ticks} tickFormatter={formatRating} stroke="#5B616A" width={32} />
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
              const lines = drop
                ? [`▼ ${monthName(change.period_start)}: pokles o ${formatRating(Math.abs(change.delta))}`, ...(change.main_topic_key ? [`Hlavní téma: ${topicName(topics, change.main_topic_key)}`] : [])]
                : [`▲ ${monthName(change.period_start)}: oživení`];
              return (
                <ReferenceDot
                  key={`dot-${change.kind}-${change.source}-${change.period_start}`}
                  x={change.period_start}
                  y={y}
                  shape={<Marker color={LINES[change.source].color} lines={lines} drop={drop} />}
                />
              );
            })}
          </LineChart>
        </ResponsiveContainer>
      </div>
      <p className="mt-2 text-sm text-muted">Zvýrazněný měsíc je pokles hodnocení o 0,5 hvězdy a víc oproti předchozímu měsíci, značka ▲ je vzestup o stejnou hodnotu.</p>
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
