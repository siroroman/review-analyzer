import { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useApi } from "../api/context";
import type { Suggestion } from "../api/client";
import { useDebounced } from "../useDebounced";
import { AppHeader } from "../components/AppHeader";
import { describeError } from "./errors";

export const DEBOUNCE_MS = 300;

/** Find a Place by its name; the user picks exactly one Place and starts a Run for it. */
export function SearchScreen() {
  const api = useApi();
  const navigate = useNavigate();
  const [text, setText] = useState("");
  const query = useDebounced(text.trim(), DEBOUNCE_MS);
  const [found, setFound] = useState<Suggestion[] | null>(null);
  const [problem, setProblem] = useState<string | null>(null);
  const [chosen, setChosen] = useState<Suggestion | null>(null);
  const [busy, setBusy] = useState(false);
  /** The text we put into the input ourselves after a pick; it needs no new suggestions. */
  const filled = useRef<string | null>(null);

  useEffect(() => {
    if (!query || query === filled.current) {
      setFound(null);
      setProblem(null);
      return;
    }
    const controller = new AbortController();
    api.suggest(query, controller.signal).then(
      (items) => {
        if (controller.signal.aborted) return;
        setFound(items);
        setProblem(null);
      },
      (error: unknown) => {
        if (controller.signal.aborted) return;
        setFound(null);
        setProblem(describeError(error, "vyhledat firmu"));
      },
    );
    return () => controller.abort();
  }, [api, query]);

  function edit(value: string) {
    setText(value);
    setChosen(null);
    filled.current = null;
  }

  function choose(suggestion: Suggestion) {
    filled.current = suggestion.text.trim();
    setText(suggestion.text);
    setChosen(suggestion);
    setFound(null);
    setProblem(null);
  }

  async function start() {
    if (!chosen) return;
    setBusy(true);
    try {
      const run = await api.startRun({ place_ids: [chosen.place_id] });
      navigate(`/runs/${run.run_id}`);
    } catch (error) {
      setProblem(describeError(error, "spustit analýzu"));
      setBusy(false);
    }
  }

  return (
    <>
      <AppHeader />
      <main className="mx-auto flex max-w-180 flex-col gap-7 px-6 pt-16 pb-12">
        <div>
          <h1 className="text-4xl leading-tight font-bold">Co o vaší firmě říkají zákazníci?</h1>
          <p className="mt-3 text-base text-muted">
            Zadejte název firmy. Za pár minut dostanete hodnocení, témata, vysvětlení poklesů a návrhy na zlepšení.
          </p>
        </div>
        <div>
          <input
            type="search"
            role="searchbox"
            aria-label="Název firmy"
            placeholder="Např. Alza cz"
            value={text}
            onChange={(event) => edit(event.target.value)}
            className="min-h-13 w-full rounded-[10px] border-2 border-google-maps bg-card px-4 text-base font-medium"
          />
          {problem && (
            <p role="alert" className="mt-3 rounded-lg bg-red-50 p-3 text-drop">
              {problem}
            </p>
          )}
          {found?.length === 0 && <p className="mt-3 text-muted">Nic jsme nenašli.</p>}
          {found && found.length > 0 && (
            <ul className="mt-1.5 overflow-hidden rounded-[10px] border border-line bg-card shadow-lg">
              {found.map((suggestion) => (
                <li key={suggestion.place_id} className="border-t border-line first:border-t-0">
                  <button type="button" onClick={() => choose(suggestion)} className="block min-h-14 w-full px-4 py-2 text-left text-[15px] font-semibold hover:bg-[#eef3fd]">
                    {suggestion.text}
                  </button>
                </li>
              ))}
            </ul>
          )}
        </div>
        <div>
          <button
            type="button"
            disabled={!chosen || busy}
            onClick={start}
            className="inline-flex min-h-13 items-center justify-center rounded-[10px] bg-ink px-7 text-base font-semibold text-white disabled:opacity-50"
          >
            Analyzovat recenze
          </button>
        </div>
      </main>
    </>
  );
}
