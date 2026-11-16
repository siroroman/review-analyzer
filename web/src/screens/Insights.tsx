import type { RunResult } from "../api/client";

/** The summary paragraph and numbered suggestions; each statement opens the Reviews it cites. */
export function Insights({ insights, onOpen }: { insights: RunResult["insights"]; onOpen: (title: string, ids: string[]) => void }) {
  const summary = insights.find((insight) => insight.type === "summary");
  const suggestions = insights.filter((insight) => insight.type === "suggestion");
  if (!summary && suggestions.length === 0) return null;

  const link = (title: string, ids: string[]) => (
    <button onClick={() => onOpen(title, ids)} className="inline-flex min-h-11 items-center text-blue-700 underline">
      {`Zobrazit recenze (${ids.length})`}
    </button>
  );

  return (
    <section className="rounded-card border border-line bg-card p-4">
      <h2 className="mb-2 text-lg font-semibold">Shrnutí a doporučení</h2>
      {summary && (
        <p className="mb-3">
          {summary.text} {link("Recenze ke shrnutí", summary.review_ids)}
        </p>
      )}
      <ol aria-label="Doporučení" className="flex flex-col gap-2">
        {suggestions.map((suggestion, index) => (
          <li key={index} className="flex gap-3 rounded border border-line p-3">
            <span aria-hidden="true" className="font-semibold">
              {index + 1}
            </span>
            <span>
              {suggestion.text} {link(`Recenze k doporučení ${index + 1}`, suggestion.review_ids)}
            </span>
          </li>
        ))}
      </ol>
      <p className="mt-3 text-sm text-muted">Každé tvrzení odkazuje na recenze, ze kterých vzniklo.</p>
    </section>
  );
}
