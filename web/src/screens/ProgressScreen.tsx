import { useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { ApiError, type RunProgress, type RunStatus } from "../api/client";
import { useApi } from "../api/context";
import { AppHeader } from "../components/AppHeader";
import { COST_KEY, FINAL, SOURCE_NAMES, STEPS, formatUsd, formatCount } from "../steps";

export const POLL_MS = 2000;

const FAILED = "Analýza selhala.";

type StepState = "done" | "active" | "todo";

/** A finished Run has done every step; for a partial or failed one we do not know which, so none is claimed. */
function stepState(index: number, current: number, final: RunStatus | null): StepState {
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

function downloadedText(downloaded: RunProgress["downloaded"]): string | null {
  const parts = Object.entries(downloaded ?? {}).map(([source, n]) => `${SOURCE_NAMES[source] ?? source} ${formatCount(n)}`);
  return parts.length ? parts.join(" · ") : null;
}

/** How many Reviews are classified, as a bar that glides between polls and as words. */
function ClassifyBar({ progress }: { progress: RunProgress }) {
  const { classified, to_classify: total, flagged } = progress;
  if (classified === null || total === null) return null;
  const share = total > 0 ? Math.min(100, Math.round((classified / total) * 1000) / 10) : 0;
  return (
    <>
      <span
        role="progressbar"
        aria-label="Třídění recenzí"
        aria-valuemin={0}
        aria-valuenow={classified}
        aria-valuemax={total}
        className="mt-2 block h-2 overflow-hidden rounded-full bg-[#eceae3]"
      >
        <span data-testid="classify-fill" className="block h-full rounded-full bg-google-maps transition-[width] duration-700 ease-out" style={{ width: `${share}%` }} />
      </span>
      <span className="mt-1.5 block text-sm text-muted">
        {formatCount(classified)} z {formatCount(total)} recenzí
        {flagged ? ` · ${formatCount(flagged)} ${flagged === 1 ? "podezřelá recenze vyřazena" : flagged < 5 ? "podezřelé recenze vyřazeny" : "podezřelých recenzí vyřazeno"}` : ""}
      </span>
    </>
  );
}

/** The share of the budget spent, 0 to 100. */
function budgetShare({ cost, budget }: RunProgress): number {
  const cap = Number(budget);
  return cap > 0 ? Math.min(100, Math.round((Number(cost) / cap) * 1000) / 10) : 0;
}

/** Done: a blue circle with a check. Running: a ring that spins, and stands still under reduced motion (the word says it). */
function Marker({ state }: { state: StepState }) {
  if (state === "done") {
    return (
      <span aria-hidden="true" data-ring="done" className="flex size-7 flex-none items-center justify-center rounded-full bg-google-maps text-white">
        <svg width="14" height="14" viewBox="0 0 14 14">
          <path d="M2 7.5l3 3 7-7" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
        </svg>
      </span>
    );
  }
  if (state === "active") {
    return <span aria-hidden="true" data-ring="active" className="size-7 flex-none rounded-full border-[3px] border-[#dce6fa] border-t-google-maps motion-safe:animate-spin" />;
  }
  return <span aria-hidden="true" data-ring="todo" className="size-7 flex-none rounded-full border-2 border-[#cfcdc4]" />;
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

  const final = progress && FINAL.includes(progress.status) ? progress.status : null;
  const current = progress ? STEPS.findIndex((step) => step.status === progress.status) : -1;

  const stateLabel = { done: "Hotovo", active: "Probíhá", todo: "Čeká" } as const;

  return (
    <>
      <AppHeader />
      <main className="mx-auto flex max-w-180 flex-col gap-6 px-6 pt-12 pb-12">
        <div>
          <h1 className="text-3xl leading-tight font-bold">{progress?.company_name ? `Analýza: ${progress.company_name}` : "Analýza"}</h1>
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
                const cost = step.status in COST_KEY ? progress.step_cost[COST_KEY[step.status as keyof typeof COST_KEY]] : null;
                const detail = step.status === "downloading" ? downloadedText(progress.downloaded) : step.hint;
                return (
                  <li
                    key={step.status}
                    data-state={state}
                    aria-current={state === "active" ? "step" : undefined}
                    className={`flex min-h-16 items-center gap-3.5 rounded-card bg-card p-4 ${state === "active" ? "border-2 border-google-maps" : "border border-line"}`}
                  >
                    <Marker state={state} />
                    <span className="flex-1">
                      <span className={`block text-[15px] font-semibold ${state === "todo" ? "text-muted" : ""}`}>{step.label}</span>
                      {detail && <span className="block text-sm text-muted">{detail}</span>}
                      {step.status === "classifying" && state !== "todo" && <ClassifyBar progress={progress} />}
                    </span>
                    <span className="text-sm text-muted">
                      {stateLabel[state]}
                      {cost && state !== "todo" ? ` · ${formatUsd(cost)}` : ""}
                    </span>
                  </li>
                );
              })}
            </ol>
            <div className="rounded-card border border-line bg-card p-4">
              <div className="flex justify-between text-sm">
                <span className="font-semibold">Průběžné náklady</span>
                <span>
                  <b>{formatUsd(progress.cost)}</b> z rozpočtu {formatUsd(progress.budget)}
                </span>
              </div>
              <span
                role="progressbar"
                aria-label="Průběžné náklady"
                aria-valuemin={0}
                aria-valuenow={Number(progress.cost)}
                aria-valuemax={Number(progress.budget)}
                className="mt-2.5 block h-2 overflow-hidden rounded-full bg-[#eceae3]"
              >
                <span data-testid="budget-fill" className="block h-full rounded-full bg-ink transition-[width] duration-700 ease-out" style={{ width: `${budgetShare(progress)}%` }} />
              </span>
              <p className="mt-2.5 text-sm text-muted">
                Při překročení rozpočtu se analýza zastaví a dostanete částečný výsledek s tím, co se stihlo.
              </p>
            </div>
            {final === "failed" && (
              <p role="status" className="rounded-card border border-line bg-card p-3">
                {FAILED}
              </p>
            )}
          </>
        )}
        <div className="flex flex-wrap gap-x-6">
          {(final === "failed" || problem?.gone) && (
            <Link to="/" className="inline-flex min-h-11 items-center text-google-maps underline">
              Nové hledání
            </Link>
          )}
        </div>
      </main>
    </>
  );
}
