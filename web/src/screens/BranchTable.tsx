import type { RunResult } from "../api/client";
import { SOURCE_LABEL, formatCount, formatRating, topicName } from "./result";

/** The branches side by side; the weakest by rating is marked with ▼ and a highlight. Needs two branches to compare. */
export function BranchTable({ result }: { result: RunResult }) {
  const rows = result.metrics.per_place.map((entry) => ({
    ...entry,
    name: result.company.places.find((place) => place.source === entry.source && place.external_id === entry.place_external_id)?.name ?? entry.place_external_id,
  }));
  if (rows.length < 2) return null;
  const weakest = rows.reduce((worst, row) => (row.summary.average_rating < worst.summary.average_rating ? row : worst));

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
              <tr key={`${row.source}:${row.place_external_id}`} className={row === weakest ? "bg-page font-semibold" : ""}>
                <td className="p-2">
                  {row === weakest && <span title="Nejslabší pobočka">▼ </span>}
                  {row.name}
                  <span className="block text-sm font-normal text-muted">{SOURCE_LABEL[row.source]}</span>
                </td>
                <td className="p-2">{formatRating(row.summary.average_rating)}</td>
                <td className="p-2" aria-label={formatCount(row.summary.count)}>
                  {row.summary.count}
                </td>
                <td className="p-2">{row.main_topic_key ? topicName(result.topics, row.main_topic_key) : "–"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}
