import type { RunResult } from "../api/client";
import { SOURCE_LABEL, formatCount, formatRating, topicName, type Source } from "./result";

const normalize = (text: string) => text.trim().toLowerCase().replace(/\s+/g, " ");

/** The branches side by side; the weakest by rating is marked with ▼ and a highlight. Needs two branches to compare. */
export function BranchTable({ result }: { result: RunResult }) {
  // One branch can be a Place on both Sources; the same address makes it one row, its rating weighted by Review count.
  const branches = new Map<string, { name: string; sources: Source[]; sum: number; count: number; topic: string | null }>();
  for (const entry of result.metrics.per_place) {
    const place = result.company.places.find((candidate) => candidate.source === entry.source && candidate.external_id === entry.place_external_id);
    const key = place ? normalize(place.address) : `${entry.source}:${entry.place_external_id}`;
    const row = branches.get(key) ?? { name: place?.name ?? entry.place_external_id, sources: [], sum: 0, count: 0, topic: null };
    row.sources.push(entry.source);
    row.sum += entry.summary.average_rating * entry.summary.count;
    row.count += entry.summary.count;
    row.topic ??= entry.main_topic_key ?? null;
    branches.set(key, row);
  }
  const rows = [...branches.entries()].map(([key, row]) => ({ ...row, key, rating: row.count === 0 ? 0 : row.sum / row.count }));
  if (rows.length < 2) return null;
  const weakest = rows.reduce((worst, row) => (row.rating < worst.rating ? row : worst));

  return (
    <section className="rounded-card border border-line bg-card p-4">
      <h2 className="mb-2 text-lg font-semibold">Srovnání poboček</h2>
      <div className="overflow-x-auto">
        <table aria-label="Srovnání poboček" className="w-full min-w-120 text-left">
          <thead>
            <tr className="text-sm text-muted">
              <th className="p-2">Pobočka</th>
              <th className="p-2">Hodnocení</th>
              <th className="p-2">Recenze</th>
              <th className="p-2">Hlavní problém</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => (
              <tr key={row.key} className={row === weakest ? "bg-page font-semibold" : ""}>
                <td className="p-2">
                  {row === weakest && <span title="Nejslabší pobočka">▼ </span>}
                  {row.name}
                  <span className="block text-sm font-normal text-muted">{row.sources.map((source) => SOURCE_LABEL[source]).join(", ")}</span>
                </td>
                <td className="p-2">{formatRating(row.rating)}</td>
                <td className="p-2" aria-label={formatCount(row.count)}>
                  {row.count}
                </td>
                <td className="p-2">{row.topic ? topicName(result.topics, row.topic) : "–"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}
