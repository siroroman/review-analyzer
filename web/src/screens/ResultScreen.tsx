import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { ApiError, type RunResult } from "../api/client";
import { useApi } from "../api/context";
import { describeError } from "./errors";

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
      {result && <h1 className="text-2xl font-semibold">{result.company.name}</h1>}
    </main>
  );
}
