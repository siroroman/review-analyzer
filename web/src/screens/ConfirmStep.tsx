import { useEffect, useState, type FormEvent } from "react";
import { useNavigate } from "react-router-dom";
import type { Branch, Suggestion } from "../api/client";
import { useApi } from "../api/context";
import { AppHeader } from "../components/AppHeader";
import { describeError } from "./errors";

/** The most Places one Run takes (`RunIn.place_ids` in the API). */
const MAX_PLACES = 20;

type Props = { suggestion: Suggestion; company: boolean; onBack: () => void };

/**
 * The last step before a Run: for a Company the found branches, which the user may remove when they are
 * false (the chosen Place stays). The API names the Company after the chosen Place and infers its industry.
 */
export function ConfirmStep({ suggestion, company, onBack }: Props) {
  const api = useApi();
  const navigate = useNavigate();
  const [branches, setBranches] = useState<Branch[] | null>(company ? null : []);
  const [removed, setRemoved] = useState<ReadonlySet<string>>(new Set());
  const [problem, setProblem] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (!company) return;
    let current = true;
    api.branches(suggestion.place_id).then(
      (items) => current && setBranches(items),
      (error: unknown) => {
        if (!current) return;
        setBranches([]);
        setProblem(describeError(error, "najít pobočky"));
      },
    );
    return () => {
      current = false;
    };
  }, [api, company, suggestion.place_id]);

  const kept = (branches ?? []).filter((branch) => !removed.has(branch.place_id));
  const selected = 1 + kept.length;
  const tooMany = selected > MAX_PLACES;

  function toggle(placeId: string) {
    setRemoved((before) => {
      const next = new Set(before);
      if (!next.delete(placeId)) next.add(placeId);
      return next;
    });
  }

  async function start(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    try {
      const run = await api.startRun({
        place_ids: [suggestion.place_id, ...kept.map((branch) => branch.place_id)],
      });
      navigate(`/runs/${run.run_id}`);
    } catch (error) {
      setProblem(describeError(error, "spustit analýzu"));
      setBusy(false);
    }
  }

  const row = "flex min-h-11 items-center gap-3";
  return (
    <>
      <AppHeader />
      <main className="mx-auto max-w-180 px-6 pt-10 pb-12">
        <button type="button" onClick={onBack} className="mb-4 inline-flex min-h-11 items-center text-google-maps underline">
          ← Zpět na hledání
        </button>
        <form onSubmit={start} className="space-y-4 rounded-card border border-line bg-card p-6">
          <h1 className="text-3xl font-bold">{company ? "Pobočky firmy" : "Jedna pobočka"}</h1>
          {company && (
            <fieldset>
              <legend className="mb-2 text-muted">Odškrtněte pobočky, které k firmě nepatří.</legend>
              {branches === null && <p>Hledáme pobočky…</p>}
              <label className={row}>
                <input type="checkbox" checked disabled className="size-5" /> {suggestion.text}
              </label>
              {branches?.length === 0 && <p className="text-muted">Žádné další pobočky jsme nenašli.</p>}
              {branches?.map((branch) => (
                <label key={branch.place_id} className={row}>
                  <input type="checkbox" className="size-5" checked={!removed.has(branch.place_id)} onChange={() => toggle(branch.place_id)} />{" "}
                  {branch.name}, {branch.address}
                </label>
              ))}
            </fieldset>
          )}
          {tooMany && (
            <p className="text-drop">
              Analyzovat lze nejvýše {MAX_PLACES} míst, vybráno {selected}. Odškrtněte ty, které k firmě nepatří.
            </p>
          )}
          {!company && <p>{suggestion.text}</p>}
          {problem && (
            <p role="alert" className="rounded-lg bg-red-50 p-3 text-drop">
              {problem}
            </p>
          )}
          <button type="submit" disabled={busy || tooMany} className="min-h-13 rounded-[10px] bg-ink px-7 text-base font-semibold text-white disabled:opacity-50">
            Spustit analýzu
          </button>
        </form>
      </main>
    </>
  );
}
