import { useEffect, useMemo, useState, type ReactNode } from "react";
import { Link, useParams } from "react-router-dom";
import { ApiError, type RunResult } from "../api/client";
import { useApi } from "../api/context";
import { AppHeader } from "../components/AppHeader";
import { rememberRun } from "../recentRuns";
import { formatCost } from "../steps";
import { describeError } from "./errors";
import { BranchTable } from "./BranchTable";
import { Insights } from "./Insights";
import { RatingDistribution } from "./RatingDistribution";
import { ReviewsPanel, type PanelRequest } from "./ReviewsPanel";
import { Timeline, monthLabel } from "./Timeline";
import { TopicsCard } from "./TopicsCard";
import { SOURCE_LABEL, topicName, formatCount, formatRating, type Source, type Summary } from "./result";

/** The Sources of the Company's Places and the months the Reviews cover. */
function sourceLine(places: { source: Source }[], trend: { period_start: string }[]): string {
  const sources = [...new Set(places.map((place) => place.source))].map((source) => SOURCE_LABEL[source]).join(", ");
  const months = trend.map((point) => point.period_start).sort();
  if (months.length === 0) return sources;
  return `${sources} · recenze od ${monthLabel(months[0]!)} do ${monthLabel(months[months.length - 1]!)}`;
}

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

  useEffect(() => {
    let stopped = false;
    setResult(null);
    setError(null);
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
      {result && <Dashboard result={result} />}
      </main>
    </>
  );
}

function Dashboard({ result }: { result: RunResult }) {
  const api = useApi();
  const { company, metrics } = result;
  const [panel, setPanel] = useState<{ topic: string | null; request: PanelRequest } | null>(null);
  const openTopic = (key: string) =>
    setPanel({ topic: key, request: { title: `Recenze: ${topicName(result.topics, key)}`, load: () => api.reviews(result.run_id, { topic: key }) } });
  const openInsight = (title: string, ids: string[]) => setPanel({ topic: null, request: { title, load: () => api.reviews(result.run_id, { ids }) } });
  const openRating = (stars: number) => setPanel({ topic: null, request: { title: `Recenze: ${stars} ★`, load: () => api.reviews(result.run_id, { rating: stars }) } });
  const closePanel = useMemo(() => () => setPanel(null), []);
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
      <p className="mb-4 mt-1 text-sm text-muted">{sourceLine(company.places, metrics.trend)}</p>
      <div className="mb-6 flex flex-wrap gap-3">
        {metrics.per_source.map(({ source, summary }) => (
          <Card key={source} label={SOURCE_LABEL[source]}>
            <Rating summary={summary} />
          </Card>
        ))}
        <Card label="Náklady analýzy">
          <p className="text-3xl font-semibold">{formatCost(result.cost)}</p>
        </Card>
      </div>
      <div className="mt-6">
        <section className="min-w-0 rounded-card border border-line bg-card p-5">
          <h2 className="mb-2 text-base font-semibold">Vývoj hodnocení</h2>
          {months === 0 ? (
            <p>Nenašli jsme žádné recenze, není co zobrazit.</p>
          ) : (
            <>
              {months === 1 && <p className="mb-2 text-sm text-muted">Zatím je k dispozici jen jeden měsíc, vývoj nejde ukázat.</p>}
              <Timeline trend={metrics.trend} changes={metrics.changes} topics={result.topics} />
            </>
          )}
        </section>
      </div>
      {metrics.topic_shares.length > 0 && (
        <div className="mt-4">
          <TopicsCard shares={metrics.topic_shares} topics={result.topics} selected={panel?.topic ?? null} onSelect={openTopic} />
        </div>
      )}
      <div className="mt-4 flex flex-col gap-4">
        <RatingDistribution counts={metrics.rating_counts} onSelect={openRating} />
        <div className="mt-6">
          <Insights insights={result.insights} onOpen={openInsight} />
        </div>
        <BranchTable result={result} />
      </div>
      {panel && <ReviewsPanel request={panel.request} onClose={closePanel} />}
    </>
  );
}
