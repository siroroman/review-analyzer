import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { ApiError, type RunProgress } from "../api/client";
import { useApi } from "../api/context";
import { FINAL, STEPS, formatCost } from "../steps";

export const POLL_MS = 2000;

const ENDINGS = {
  done: "Hotovo. Analýza je dokončená.",
  partial: "Částečný výsledek: analýza skončila dřív (limit nákladů nebo chyba kroku), ukážeme, co se stihlo.",
  failed: "Analýza selhala.",
} as const;

type StepState = "done" | "active" | "todo";

/** A finished Run has done every step; for a partial or failed one we do not know which, so none is claimed. */
function stepState(index: number, current: number, final: keyof typeof ENDINGS | null): StepState {
  if (final === "done") return "done";
  if (final) return "todo";
  return index < current ? "done" : index === current ? "active" : "todo";
}

/** Where a Run is. The state lives on the server, so opening the same link again resumes the view. */
export function ProgressScreen() {
  const api = useApi();
  const { id = "" } = useParams();
  const [progress, setProgress] = useState<RunProgress | null>(null);
  const [problem, setProblem] = useState<string | null>(null);

  useEffect(() => {
    let timer: ReturnType<typeof setTimeout> | undefined;
    let stopped = false;

    async function poll() {
      let again = true;
      try {
        const latest = await api.runProgress(id);
        if (stopped) return;
        setProgress(latest);
        setProblem(null);
        again = !FINAL.includes(latest.status);
      } catch (error) {
        if (stopped) return;
        const status = error instanceof ApiError ? error.status : 0;
        again = status !== 401 && status !== 404;
        setProblem(
          status === 404
            ? "Tato analýza neexistuje."
            : status === 401
              ? "Chybí platný odkaz s přístupem. Otevřete prosím odkaz, který jste dostali."
              : "Spojení se serverem se přerušilo, zkoušíme to znovu.",
        );
      }
      if (again && !stopped) timer = setTimeout(poll, POLL_MS);
    }

    void poll();
    return () => {
      stopped = true;
      clearTimeout(timer);
    };
  }, [api, id]);

  const final = progress && FINAL.includes(progress.status) ? (progress.status as keyof typeof ENDINGS) : null;
  const current = progress ? STEPS.findIndex((step) => step.status === progress.status) : -1;

  return (
    <main className="mx-auto max-w-xl p-6">
      <h1 className="mb-4 text-2xl font-semibold">Průběh analýzy</h1>
      {problem && (
        <p role="alert" className="mb-4 rounded bg-red-50 p-3 text-red-800">
          {problem}
        </p>
      )}
      {progress && (
        <>
          <ol className="mb-4 space-y-2">
            {STEPS.map((step, index) => {
              const state = stepState(index, current, final);
              return (
                <li
                  key={step.status}
                  data-state={state}
                  aria-current={state === "active" ? "step" : undefined}
                  className={state === "todo" ? "text-gray-400" : state === "done" ? "text-green-700" : "font-semibold"}
                >
                  <span aria-hidden="true">{state === "done" ? "✓ " : state === "active" ? "… " : "○ "}</span>
                  <span>{step.label}</span>
                </li>
              );
            })}
          </ol>
          <p className="mb-4">Dosavadní náklady: {formatCost(progress.cost)}</p>
          {final && (
            <p role="status" className="rounded bg-gray-100 p-3">
              {ENDINGS[final]}
            </p>
          )}
        </>
      )}
      {(final === "done" || final === "partial") && (
        <Link to={`/runs/${id}/result`} className="mt-4 mr-4 inline-flex min-h-11 items-center font-semibold text-blue-700 underline">
          Zobrazit výsledek
        </Link>
      )}
      {(final || problem === "Tato analýza neexistuje.") && (
        <Link to="/" className="mt-4 inline-block text-blue-700 underline">
          Nové hledání
        </Link>
      )}
    </main>
  );
}
