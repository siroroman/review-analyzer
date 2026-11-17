import type { Metrics } from "../api/client";
import { formatCount } from "./result";

const percent = (count: number, total: number) => Math.round((count / total) * 100);

/** How many Reviews gave 5 down to 1 stars; a row opens the Reviews with that rating. */
export function RatingDistribution({
  counts,
  onSelect,
}: {
  counts: Metrics["rating_counts"];
  onSelect: (stars: number) => void;
}) {
  const total = counts.reduce((sum, entry) => sum + entry.count, 0);
  if (total === 0) return null;
  const high = counts.filter((entry) => entry.stars >= 4).reduce((sum, entry) => sum + entry.count, 0);
  return (
    <section role="group" aria-label="Rozdělení hodnocení" className="rounded-card border border-line bg-card p-5">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <h2 className="text-base font-semibold">Rozdělení hodnocení</h2>
        <span className="text-sm text-muted">Všech {formatCount(total)}</span>
      </div>
      <ul className="mt-4 flex flex-col gap-1">
        {counts.map(({ stars, count }) => (
          <li key={stars}>
            <button
              onClick={() => onSelect(stars)}
              aria-label={`${stars} ★, ${formatCount(count)}, ${percent(count, total)} %`}
              className="flex min-h-11 w-full items-center gap-3 rounded-lg px-2 text-left text-sm hover:bg-page"
            >
              <span className="w-11 flex-none font-semibold">{stars} ★</span>
              <span aria-hidden="true" className="h-3.5 min-w-0 flex-1 rounded-full bg-[#eceae3]">
                <span className={`block h-3.5 rounded-full bg-ink`} style={{ width: `${percent(count, total)}%` }} />
              </span>
              <span className="w-24 flex-none text-right text-muted">
                {count} · {percent(count, total)} %
              </span>
            </button>
          </li>
        ))}
      </ul>
      <p className="mt-3 text-sm text-muted">{percent(high, total)} % recenzí má 4 nebo 5 hvězdiček. Kliknutím na řádek zobrazíte recenze s tímto hodnocením.</p>
    </section>
  );
}
