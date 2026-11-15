import { useEffect, useState, type FormEvent } from "react";
import { useNavigate } from "react-router-dom";
import type { Branch, Suggestion } from "../api/client";
import { useApi } from "../api/context";
import { describeError } from "./errors";

/** The most Places one Run takes (`RunIn.place_ids` in the API). */
const MAX_PLACES = 20;

type Props = { suggestion: Suggestion; company: boolean; onBack: () => void };

/** "Kavárna Slavia, Praha" -> "Kavárna Slavia": the name before the first comma. */
const nameOf = (text: string) => text.split(",")[0]?.trim() ?? text;

/**
 * The last step before a Run: for a Company the found branches, which the user may remove when they are
 * false (the chosen Place stays), then the name and industry.
 */
export function ConfirmStep({ suggestion, company, onBack }: Props) {
  const api = useApi();
  const navigate = useNavigate();
  const [branches, setBranches] = useState<Branch[] | null>(company ? null : []);
  const [removed, setRemoved] = useState<ReadonlySet<string>>(new Set());
  const [name, setName] = useState(nameOf(suggestion.text));
  const [industry, setIndustry] = useState("");
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
    if (!name.trim() || !industry.trim()) {
      setProblem("Vyplňte název firmy a obor.");
      return;
    }
    setBusy(true);
    try {
      const run = await api.startRun({
        place_ids: [suggestion.place_id, ...kept.map((branch) => branch.place_id)],
        name: name.trim(),
        industry: industry.trim(),
      });
      navigate(`/runs/${run.run_id}`);
    } catch (error) {
      setProblem(describeError(error, "spustit analýzu"));
      setBusy(false);
    }
  }

  return (
    <main className="mx-auto max-w-xl p-6">
      <button type="button" onClick={onBack} className="mb-4 text-blue-700 underline">
        ← Zpět na hledání
      </button>
      <form onSubmit={start} className="space-y-4">
        <h1 className="text-2xl font-semibold">{company ? "Pobočky firmy" : "Jedna pobočka"}</h1>
        {company && (
          <fieldset>
            <legend className="mb-2 text-gray-600">Odškrtněte pobočky, které k firmě nepatří.</legend>
            {branches === null && <p>Hledáme pobočky…</p>}
            <label className="block">
              <input type="checkbox" checked disabled /> {suggestion.text}
            </label>
            {branches?.length === 0 && <p className="text-gray-600">Žádné další pobočky jsme nenašli.</p>}
            {branches?.map((branch) => (
              <label key={branch.place_id} className="block">
                <input
                  type="checkbox"
                  checked={!removed.has(branch.place_id)}
                  onChange={() => toggle(branch.place_id)}
                />{" "}
                {branch.name}, {branch.address}
              </label>
            ))}
          </fieldset>
        )}
        {tooMany && (
          <p className="text-red-800">
            Analyzovat lze nejvýše {MAX_PLACES} míst, vybráno {selected}. Odškrtněte ty, které k firmě nepatří.
          </p>
        )}
        {!company && <p>{suggestion.text}</p>}
        <label className="block">
          Název firmy
          <input value={name} onChange={(event) => setName(event.target.value)} maxLength={100} className="mt-1 w-full rounded border p-2" />
        </label>
        <label className="block">
          Obor
          <input value={industry} onChange={(event) => setIndustry(event.target.value)} maxLength={60} className="mt-1 w-full rounded border p-2" />
        </label>
        {problem && (
          <p role="alert" className="rounded bg-red-50 p-3 text-red-800">
            {problem}
          </p>
        )}
        <button type="submit" disabled={busy || tooMany} className="rounded bg-blue-700 px-4 py-2 text-white disabled:opacity-50">
          Spustit analýzu
        </button>
      </form>
    </main>
  );
}
