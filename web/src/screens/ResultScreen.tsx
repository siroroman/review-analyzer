import { useEffect, useMemo, useState, type ReactNode } from "react";
import { Link, useParams } from "react-router-dom";
import { ApiError, type RunResult } from "../api/client";
import { useApi } from "../api/context";
import { AppHeader } from "../components/AppHeader";
import { rememberRun } from "../recentRuns";
import { formatCost } from "../steps";
import { describeError } from "./errors";
import { BranchTable } from "./BranchTable";
import { CostCard } from "./CostCard";
import { Insights } from "./Insights";
import { RatingDistribution } from "./RatingDistribution";
import { ReviewsPanel, type PanelRequest } from "./ReviewsPanel";
import { Timeline } from "./Timeline";
import { TopicsCard } from "./TopicsCard";
import { SOURCE_LABEL, topicName, changeAgainstPreviousYear, formatChange, formatCount, formatRating, type Source, type Summary } from "./result";

const WHOLE_COMPANY = "all";

/** The Sources of the Company's Places and the period the Reviews cover. */
function sourceLine(places: { source: Source }[]): string {
  const sources = [...new Set(places.map((place) => place.source))];
  return `${sources.map((source) => SOURCE_LABEL[source]).join(", ")} · recenze za posledních 12 měsíců`;
}

function Card({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div role="group" aria-label={label} className="min-w-40 flex-1 rounded-card border border-line bg-card p-4">
      <p className="mb-1 text-sm text-muted">{label}</p>
      {children}
    </div>
  );
}

function Rating({ summary, outOf }: { summary: Summary | null | undefined; outOf?: number }) {
  const count = formatCount(summary?.count ?? 0);
  return (
    <>
      <p className="text-3xl font-semibold">{summary ? formatRating(summary.average_rating) : "–"}</p>
      {outOf === undefined ? (
        <p className="text-sm text-muted">{count}</p>
      ) : (
        <p className="text-sm text-muted">
          <span>/ {outOf} ·</span> <span>{count}</span>
        </p>
      )}
    </>
  );
}

/** The change against the previous 12 months, marked by an arrow and the sign, never by colour alone. */
function ChangeLine({ change }: { change: number }) {
  const rounded = Math.round(change * 10) / 10;
  const arrow = rounded > 0 ? "▲" : rounded < 0 ? "▼" : "";
  const color = rounded > 0 ? "text-rise" : rounded < 0 ? "text-[#8a3f00]" : "text-muted";
  return (
    <p className={`mt-1 text-sm font-semibold ${color}`}>
      {arrow && <span aria-hidden="true">{arrow} </span>}
      {formatChange(change)}
    </p>
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
      (loaded) => {
        if (stopped) return;
        setResult(loaded);
        rememberRun(id, loaded.company.name);
      },
      (failed) => !stopped && setError(failed),
    );
    return () => {
      stopped = true;
    };
  }, [api, id]);

  const status = error instanceof ApiError ? error.status : 0;

  return (
    <>
      <AppHeader>
        {result && <span>Analýza dokončena · výsledek v cache 24 h</span>}
        <Link to="/" className="inline-flex min-h-11 items-center rounded-lg border border-[#cfcdc4] bg-card px-4 font-semibold text-ink no-underline">
          Nové hledání
        </Link>
      </AppHeader>
      <main className="mx-auto max-w-7xl px-4 pb-12 pt-7 sm:px-6">
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
    </>
  );
}

function Dashboard({ result, tab, onTab }: { result: RunResult; tab: string; onTab: (tab: string) => void }) {
  const api = useApi();
  const { company, metrics } = result;
  const [panel, setPanel] = useState<{ topic: string | null; request: PanelRequest } | null>(null);
  const openTopic = (key: string) =>
    setPanel({ topic: key, request: { title: `Recenze: ${topicName(result.topics, key)}`, load: () => api.reviews(result.run_id, { topic: key }) } });
  const openInsight = (title: string, ids: string[]) => setPanel({ topic: null, request: { title, load: () => api.reviews(result.run_id, { ids }) } });
  const openRating = (stars: number) => setPanel({ topic: null, request: { title: `Recenze: ${stars} ★`, load: () => api.reviews(result.run_id, { rating: stars }) } });
  const closePanel = useMemo(() => () => setPanel(null), []);
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
      <h1 className="text-2xl font-semibold">{company.name}</h1>
      <p className="mb-3 mt-1 text-sm text-muted">{sourceLine(company.places)}</p>
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
          <Rating summary={overall} outOf={5} />
          {change !== null && <ChangeLine change={change} />}
        </Card>
        <Card label="Podezřelé recenze">
          <p className="text-3xl font-semibold">{result.flagged}</p>
          <p className="text-sm text-muted">vyřazeno z analýzy</p>
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
      <div className="mt-6 grid items-stretch gap-4 lg:grid-cols-[minmax(0,1fr)_340px]">
        <section className="min-w-0 rounded-card border border-line bg-card p-5">
          <h2 className="mb-2 text-base font-semibold">Vývoj hodnocení</h2>
          {place && <p className="mb-2 text-sm text-muted">Časová osa ukazuje celou firmu.</p>}
          {months === 0 ? (
            <p>Nenašli jsme žádné recenze, není co zobrazit.</p>
          ) : (
            <>
              {months === 1 && <p className="mb-2 text-sm text-muted">Zatím je k dispozici jen jeden měsíc, vývoj nejde ukázat.</p>}
              <Timeline trend={metrics.trend} changes={metrics.changes} topics={result.topics} />
            </>
          )}
        </section>
        {metrics.topic_shares.length > 0 && <TopicsCard shares={metrics.topic_shares} topics={result.topics} selected={panel?.topic ?? null} onSelect={openTopic} />}
      </div>
      <div className="mt-4 flex flex-col gap-4">
        <RatingDistribution counts={metrics.rating_counts} wholeCompany={place !== undefined} onSelect={openRating} />
        <Insights insights={result.insights} onOpen={openInsight} />
        <BranchTable result={result} />
        <CostCard byService={result.cost_by_service} flagged={result.flagged} />
      </div>
      {panel && <ReviewsPanel request={panel.request} onClose={closePanel} />}
    </>
  );
}
