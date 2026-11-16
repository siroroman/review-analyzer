import { useEffect, useState, type ReactNode } from "react";
import { Link, useParams } from "react-router-dom";
import { ApiError, type RunResult } from "../api/client";
import { useApi } from "../api/context";
import { formatCost } from "../steps";
import { describeError } from "./errors";
import { Timeline } from "./Timeline";
import { SOURCE_LABEL, changeAgainstPreviousYear, formatChange, formatCount, formatRating, type Source, type Summary } from "./result";

const WHOLE_COMPANY = "all";

function Card({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div role="group" aria-label={label} className="min-w-40 flex-1 rounded-card border border-line bg-card p-4">
      <p className="mb-1 text-sm text-muted">{label}</p>
      {children}
    </div>
  );
}

function Rating({ summary }: { summary: Summary | null | undefined }) {
  return (
    <>
      <p className="text-3xl font-semibold">{summary ? formatRating(summary.average_rating) : "–"}</p>
      <p className="text-sm text-muted">{formatCount(summary?.count ?? 0)}</p>
    </>
  );
}

/** The result of a finished Run. The Run lives on the server, so opening the link again shows the same result. */
export function ResultScreen() {
  const api = useApi();
  const { id = "" } = useParams();
  const [result, setResult] = useState<RunResult | null>(null);
  const [error, setError] = useState<unknown>(null);
  const [tab, setTab] = useState(WHOLE_COMPANY);

  useEffect(() => {
    let stopped = false;
    setResult(null);
    setError(null);
    setTab(WHOLE_COMPANY);
    api.runResult(id).then(
      (loaded) => !stopped && setResult(loaded),
      (failed) => !stopped && setError(failed),
    );
    return () => {
      stopped = true;
    };
  }, [api, id]);

  const status = error instanceof ApiError ? error.status : 0;

  return (
    <main className="mx-auto max-w-5xl p-4 sm:p-6">
      <header className="mb-4 flex flex-wrap items-center justify-between gap-2">
        <Link to="/" className="inline-flex min-h-11 items-center text-blue-700 underline">
          Nové hledání
        </Link>
      </header>
      {error !== null && (
        <div role="alert" className="mb-4 rounded bg-red-50 p-3 text-red-800">
          {status === 404
            ? "Tato analýza neexistuje."
            : status === 409
              ? "Analýza ještě neskončila, výsledek zatím není k dispozici."
              : describeError(error, "načíst výsledek")}
          {status === 409 && (
            <Link to={`/runs/${id}`} className="ml-2 inline-flex min-h-11 items-center underline">
              Zobrazit průběh
            </Link>
          )}
        </div>
      )}
      {result && <Dashboard result={result} tab={tab} onTab={setTab} />}
    </main>
  );
}

function Dashboard({ result, tab, onTab }: { result: RunResult; tab: string; onTab: (tab: string) => void }) {
  const { company, metrics } = result;
  const places = company.places.map((place) => ({ ...place, key: `${place.source}:${place.external_id}` }));
  const place = places.find((candidate) => candidate.key === tab);

  const summaryOf = (source: Source, externalId: string) =>
    metrics.per_place.find((entry) => entry.source === source && entry.place_external_id === externalId)?.summary;

  const overall = place ? summaryOf(place.source, place.external_id) : metrics.overall;
  const sources: { source: Source; summary: Summary }[] = place
    ? [{ source: place.source, summary: overall ?? { average_rating: 0, count: 0 } }]
    : metrics.per_source;
  const totalReviews = sources.reduce((sum, entry) => sum + entry.summary.count, 0);
  const change = place ? null : changeAgainstPreviousYear(metrics.trend);
  const months = new Set(metrics.trend.map((point) => point.period_start)).size;

  return (
    <>
      {result.status === "partial" && (
        <p role="status" className="mb-4 rounded-card border border-line bg-card p-3">
          Částečný výsledek: analýza skončila dřív (limit nákladů nebo chyba kroku), ukazujeme jen to, co se stihlo.
        </p>
      )}
      {result.notes.includes("industry_fallback") && (
        <p role="status" className="mb-4 rounded-card border border-line bg-card p-3">
          Obor firmy se nepodařilo určit, proto jsme použili obecná témata recenzí.
        </p>
      )}
      <h1 className="mb-3 text-2xl font-semibold">{company.name}</h1>
      <div role="tablist" aria-label="Pobočky" className="mb-4 flex flex-wrap gap-2">
        {[{ key: WHOLE_COMPANY, label: "Celá firma" }, ...places.map((entry) => ({ key: entry.key, label: `${entry.name} · ${SOURCE_LABEL[entry.source]}` }))].map(
          (entry) => (
            <button
              key={entry.key}
              role="tab"
              aria-selected={tab === entry.key}
              onClick={() => onTab(entry.key)}
              className={`min-h-11 rounded-full border px-4 ${tab === entry.key ? "border-ink bg-ink text-white" : "border-line bg-card"}`}
            >
              {entry.label}
            </button>
          ),
        )}
      </div>
      <div className="mb-6 flex flex-wrap gap-3">
        <Card label="Celkové hodnocení">
          <Rating summary={overall} />
          {change !== null && <p className="text-sm">{formatChange(change)}</p>}
        </Card>
        {sources.map(({ source, summary }) => (
          <Card key={source} label={SOURCE_LABEL[source]}>
            <Rating summary={summary} />
            <p className="text-sm">{totalReviews === 0 ? 0 : Math.round((summary.count / totalReviews) * 100)} %</p>
            <div aria-hidden="true" className="mt-1 h-2 rounded bg-line">
              <div className="h-2 rounded bg-ink" style={{ width: `${totalReviews === 0 ? 0 : (summary.count / totalReviews) * 100}%` }} />
            </div>
          </Card>
        ))}
        <Card label="Náklady analýzy">
          <p className="text-3xl font-semibold">{formatCost(result.cost)}</p>
        </Card>
      </div>
      <h2 className="mb-2 text-lg font-semibold">Vývoj hodnocení</h2>
      {place && <p className="mb-2 text-sm text-muted">Časová osa ukazuje celou firmu.</p>}
      {months === 0 ? (
        <p className="rounded-card border border-line bg-card p-4">Nenašli jsme žádné recenze, není co zobrazit.</p>
      ) : (
        <>
          {months === 1 && <p className="mb-2 text-sm text-muted">Zatím je k dispozici jen jeden měsíc, vývoj nejde ukázat.</p>}
          <Timeline trend={metrics.trend} changes={metrics.changes} topics={result.topics} />
        </>
      )}
    </>
  );
}
