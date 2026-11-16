import { useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { ApiError, type RunProgress } from "../api/client";
import { useApi } from "../api/context";
import { AppHeader } from "../components/AppHeader";
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

/** What a failed poll means for the user; `gone` means the Run cannot be shown and a new search is the way on. */
function describe(status: number): { message: string; gone: boolean } {
  if (status === 404) return { message: "Tato analýza neexistuje.", gone: true };
  if (status === 401) return { message: "Chybí platný odkaz s přístupem. Otevřete prosím odkaz, který jste dostali.", gone: false };
  if (status === 429) return { message: "Příliš mnoho požadavků, chvíli počkáme a zkusíme to znovu.", gone: false };
  if (status >= 500) return { message: "Chyba na straně serveru, zkoušíme to znovu.", gone: false };
  return { message: "Spojení se serverem se přerušilo, zkoušíme to znovu.", gone: false };
}

/** Where a Run is. The state lives on the server, so opening the same link again resumes the view. */
export function ProgressScreen() {
  const api = useApi();
  const { id = "" } = useParams();
  const [progress, setProgress] = useState<RunProgress | null>(null);
  const [problem, setProblem] = useState<{ message: string; gone: boolean } | null>(null);
  const navigate = useNavigate();

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
        if (latest.status === "done" || latest.status === "partial") {
          navigate(`/runs/${id}/result`, { replace: true });
        }
      } catch (error) {
        if (stopped) return;
        const status = error instanceof ApiError ? error.status : 0;
        again = status !== 401 && status !== 404;
        setProblem(describe(status));
      }
      if (again && !stopped) timer = setTimeout(poll, POLL_MS);
    }

    void poll();
    return () => {
      stopped = true;
      clearTimeout(timer);
    };
  }, [api, id, navigate]);

  const final = progress && FINAL.includes(progress.status) ? (progress.status as keyof typeof ENDINGS) : null;
  const current = progress ? STEPS.findIndex((step) => step.status === progress.status) : -1;

  const stateLabel = { done: "Hotovo", active: "Probíhá", todo: "Čeká" } as const;

  return (
    <>
      <AppHeader />
      <main className="mx-auto flex max-w-180 flex-col gap-6 px-6 pt-12 pb-12">
        <div>
          <h1 className="text-3xl leading-tight font-bold">Průběh analýzy</h1>
          <p className="mt-2 text-[15px] text-muted">Stránku můžete zavřít. Výsledek zůstane dostupný na tomto odkazu.</p>
        </div>
        {problem && (
          <p role="alert" className="rounded-lg bg-red-50 p-3 text-drop">
            {problem.message}
          </p>
        )}
        {progress && (
          <>
            {progress.status === "queued" && <p className="text-muted">Analýza čeká ve frontě.</p>}
            <ol className="flex flex-col gap-2.5">
              {STEPS.map((step, index) => {
                if (step.status === "queued") return null;
                const state = stepState(index, current, final);
                return (
                  <li
                    key={step.status}
                    data-state={state}
                    aria-current={state === "active" ? "step" : undefined}
                    className={`flex min-h-16 items-center gap-3.5 rounded-card bg-card p-4 ${state === "active" ? "border-2 border-google-maps" : "border border-line"}`}
                  >
                    <span aria-hidden="true" className="flex size-7 flex-none items-center justify-center rounded-full border-2 border-line text-sm">
                      {state === "done" ? "✓" : state === "active" ? "…" : ""}
                    </span>
                    <span className={`flex-1 text-[15px] font-semibold ${state === "todo" ? "text-muted" : ""}`}>{step.label}</span>
                    <span className="text-sm text-muted">{stateLabel[state]}</span>
                  </li>
                );
              })}
            </ol>
            <div className="rounded-card border border-line bg-card p-4">
              <div className="flex justify-between text-sm">
                <span className="font-semibold">Průběžné náklady</span>
                <b>{formatCost(progress.cost)}</b>
              </div>
              <p className="mt-2.5 text-sm text-muted">
                Při překročení rozpočtu se analýza zastaví a dostanete částečný výsledek s tím, co se stihlo.
              </p>
            </div>
            {final && (
              <p role="status" className="rounded-card border border-line bg-card p-3">
                {ENDINGS[final]}
              </p>
            )}
          </>
        )}
        <div className="flex flex-wrap gap-x-6">
          {(final || problem?.gone) && (
            <Link to="/" className="inline-flex min-h-11 items-center text-google-maps underline">
              Nové hledání
            </Link>
          )}
        </div>
      </main>
    </>
  );
}
