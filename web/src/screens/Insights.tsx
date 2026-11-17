import type { ReactNode } from "react";
import type { RunResult } from "../api/client";

/** Text between `**` markers is the important part of a statement: it is shown in bold. */
function highlighted(text: string): ReactNode[] {
  return text.split(/\*\*(.+?)\*\*/g).map((part, index) => (index % 2 === 1 ? <strong key={index}>{part}</strong> : part));
}

/** The summary paragraph and numbered suggestions; each statement opens the Reviews it cites. */
export function Insights({ insights, onOpen }: { insights: RunResult["insights"]; onOpen: (title: string, ids: string[]) => void }) {
  const summary = insights.find((insight) => insight.type === "summary");
  const suggestions = insights.filter((insight) => insight.type === "suggestion");
  if (!summary && suggestions.length === 0) return null;

  const button = (title: string, ids: string[]) => (
    <div className="mt-2 flex justify-end">
      <button onClick={() => onOpen(title, ids)} className="inline-flex min-h-11 items-center rounded-lg bg-ink px-4 font-semibold text-white">
        {`Zobrazit recenze (${ids.length})`}
      </button>
    </div>
  );

  return (
    <section className="rounded-card border border-line bg-card p-4">
      <h2 className="mb-2 text-lg font-semibold">Shrnutí a doporučení</h2>
      {summary && (
        <div className="mb-4 pr-3">
          <p>{highlighted(summary.text)}</p>
          {button("Recenze ke shrnutí", summary.review_ids)}
        </div>
      )}
      <ol aria-label="Doporučení" className="flex flex-col gap-2">
        {suggestions.map((suggestion, index) => (
          <li key={index} className="flex gap-3 rounded-lg bg-page p-3">
            <span aria-hidden="true" className="w-4 flex-none font-semibold">
              {index + 1}
            </span>
            <div className="min-w-0 flex-1">
              <p>{highlighted(suggestion.text)}</p>
              {button(`Recenze k doporučení ${index + 1}`, suggestion.review_ids)}
            </div>
          </li>
        ))}
      </ol>
    </section>
  );
}
