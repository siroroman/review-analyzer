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
import { SOURCE_LABEL, topicName, formatCount, formatNumber, formatRating, type Source } from "./result";

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

function Rating({ rating, count }: { rating: number | null; count: number }) {
  return (
    <>
      <p className="text-3xl font-semibold">{rating === null ? "–" : formatRating(rating)}</p>
      <p className="text-sm text-muted">{formatCount(count)}</p>
    </>
  );
}

type PlaceTotals = RunResult["places"][number];

const EXTERNAL = { target: "_blank", rel: "noopener noreferrer" } as const;
const LINK = "inline-flex min-h-11 items-center underline";

/** What Google Maps says about the Place; a missing field is simply left out. */
function PlaceHeader({ place, name }: { place: PlaceTotals; name: string }) {
  const facts = [place.category, place.address, place.phone].filter((fact): fact is string => !!fact);
  if (facts.length === 0 && !place.website && !place.maps_url && !place.thumbnail_url) return null;
  return (
    <section role="group" aria-label="Údaje o místě" className="mb-4 flex flex-wrap items-center gap-4">
      {place.thumbnail_url && <img src={place.thumbnail_url} alt={name} className="h-20 w-20 flex-none rounded-card object-cover" />}
      <div className="min-w-0 text-sm">
        {facts.map((fact) => (
          <p key={fact}>{fact}</p>
        ))}
        <div className="flex flex-wrap gap-x-4">
          {place.website && (
            <a href={place.website} {...EXTERNAL} className={LINK}>
              {websiteLabel(place.website)}
            </a>
          )}
          {place.maps_url && (
            <a href={place.maps_url} {...EXTERNAL} className={LINK}>
              Otevřít v Google Maps
            </a>
          )}
        </div>
      </div>
    </section>
  );
}

/** The host of a website without `www.`, or the address itself when it is not a valid URL. */
function websiteLabel(website: string): string {
  try {
    return new URL(website).hostname.replace(/^www\./, "");
  } catch {
    return website;
  }
}

/** The Google Maps count per star as the 5 to 1 rows of the distribution. */
function starCounts(perRating: Record<string, number>): { stars: number; count: number }[] {
  return [5, 4, 3, 2, 1].map((stars) => ({ stars, count: perRating[stars] ?? 0 }));
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
  const google = metrics.per_source.find((entry) => entry.source === "google_maps");
  const place = result.places.find((entry) => entry.source === "google_maps");
  const placeName = company.places.find((entry) => entry.source === "google_maps" && entry.external_id === place?.place_external_id)?.name ?? company.name;
  const hasTotals = google !== undefined && place !== undefined && place.rating !== null && place.review_count !== null;
  const rating = hasTotals ? place.rating : (google?.summary.average_rating ?? null);
  const reviewCount = hasTotals ? place.review_count! : (google?.summary.count ?? 0);
  const distribution = hasTotals && place.reviews_per_rating ? starCounts(place.reviews_per_rating) : metrics.rating_counts;
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
      {place && <PlaceHeader place={place} name={placeName} />}
      <div className="mb-4 flex flex-wrap gap-3">
        {google && (
          <Card label={SOURCE_LABEL.google_maps}>
            <Rating rating={rating} count={reviewCount} />
          </Card>
        )}
        <Card label="Náklady analýzy">
          <p className="text-3xl font-semibold">{formatCost(result.cost)}</p>
        </Card>
      </div>
      {hasTotals && place.analyzed_is_limited && (
        <p role="status" className="mb-4 rounded-card border border-line bg-card p-3">
          Na Google Maps je {formatNumber(place.review_count!)} hodnocení, analyzujeme posledních {formatNumber(place.analyzed_count)}.
        </p>
      )}
      <div className="mb-6">
        <RatingDistribution counts={distribution} onSelect={openRating} />
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
        <div className="mt-6">
          <Insights insights={result.insights} onOpen={openInsight} />
        </div>
        <BranchTable result={result} />
      </div>
      {panel && <ReviewsPanel request={panel.request} onClose={closePanel} />}
    </>
  );
}
