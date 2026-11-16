import { formatCost } from "../steps";
import { SERVICE_LABEL, formatExcluded } from "./result";

/** The cost of the Run per Service and the number of Flagged Reviews left out of the analysis. */
export function CostCard({ byService, flagged }: { byService: Record<string, string> | undefined; flagged: number }) {
  const entries = Object.entries(byService ?? {});
  return (
    <div role="group" aria-label="Náklady podle služeb" className="rounded-card border border-line bg-card p-4">
      <h2 className="mb-2 text-lg font-semibold">Náklady podle služeb</h2>
      {entries.length === 0 ? (
        <p className="text-sm text-muted">Rozpis zatím není k dispozici.</p>
      ) : (
        <dl className="grid grid-cols-[1fr_auto] gap-x-4 gap-y-1">
          {entries.map(([service, cost]) => (
            <div key={service} className="contents">
              <dt>{SERVICE_LABEL[service] ?? service}</dt>
              <dd className="text-right">{formatCost(cost)}</dd>
            </div>
          ))}
        </dl>
      )}
      <p className="mt-3 text-sm">{formatExcluded(flagged)}</p>
    </div>
  );
}
