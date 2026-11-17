import type { Metrics } from "../api/client";
import { formatMentions, topicName } from "./result";

const percent = (part: number, total: number) => (total === 0 ? 0 : Math.round((part / total) * 100));

/** One row per Topic: its mentions and the positive and negative share. A row opens the Reviews of the Topic. */
export function TopicsCard({
  shares,
  topics,
  selected,
  onSelect,
}: {
  shares: Metrics["topic_shares"];
  topics: ReadonlyArray<{ key: string; name: string }>;
  selected: string | null;
  onSelect: (key: string) => void;
}) {
  return (
    <section className="rounded-card border border-line bg-card p-4">
      <h2 className="mb-2 text-lg font-semibold">Témata</h2>
      <ul aria-label="Témata" className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
        {shares.map((share) => {
          const total = share.positive + share.neutral + share.negative;
          const name = topicName(topics, share.topic_key);
          const isSelected = selected === share.topic_key;
          return (
            <li key={share.topic_key}>
              <button
                aria-pressed={isSelected}
                onClick={() => onSelect(share.topic_key)}
                className={`block min-h-11 w-full rounded border p-2 text-left ${isSelected ? "border-ink bg-page" : "border-line"}`}
              >
                <span className="flex justify-between gap-2">
                  <span className="font-semibold">{name}</span>
                  <span className="text-sm text-muted">{formatMentions(total)}</span>
                </span>
                <span aria-hidden="true" className="mt-1 flex h-2 overflow-hidden rounded bg-line">
                  <span className="bg-positive" style={{ width: `${percent(share.positive, total)}%` }} />
                  <span className="bg-neutral" style={{ width: `${percent(share.neutral, total)}%` }} />
                  <span className="bg-negative" style={{ width: `${percent(share.negative, total)}%` }} />
                </span>
                <span className="text-sm">{`${percent(share.positive, total)} % pozitivních, ${percent(share.negative, total)} % negativních`}</span>
              </button>
            </li>
          );
        })}
      </ul>
    </section>
  );
}
