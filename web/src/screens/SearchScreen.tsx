import { useEffect, useState } from "react";
import { useApi } from "../api/context";
import type { Suggestion } from "../api/client";
import { useDebounced } from "../useDebounced";
import { AppHeader } from "../components/AppHeader";
import { ConfirmStep } from "./ConfirmStep";
import { describeError } from "./errors";

export const DEBOUNCE_MS = 300;

type Choice = { suggestion: Suggestion; company: boolean };

/** Find a Place by its name; the user picks exactly one Place or one Company. */
export function SearchScreen() {
  const api = useApi();
  const [text, setText] = useState("");
  const query = useDebounced(text.trim(), DEBOUNCE_MS);
  const [found, setFound] = useState<Suggestion[] | null>(null);
  const [problem, setProblem] = useState<string | null>(null);
  const [choice, setChoice] = useState<Choice | null>(null);

  useEffect(() => {
    if (!query) {
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

  if (choice) return <ConfirmStep {...choice} onBack={() => setChoice(null)} />;

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
          <label htmlFor="company-query" className="mb-1.5 block text-sm font-semibold">
            Firma nebo pobočka
          </label>
          <input
            id="company-query"
            type="search"
            role="searchbox"
            placeholder="Například název firmy"
            value={text}
            onChange={(event) => setText(event.target.value)}
            className="min-h-13 w-full rounded-[10px] border-2 border-google-maps bg-card px-4 text-base font-medium"
          />
          {problem && (
            <p role="alert" className="mt-3 rounded-lg bg-red-50 p-3 text-drop">
              {problem}
            </p>
          )}
          {found?.length === 0 && <p className="mt-3 text-muted">Nic jsme nenašli.</p>}
          {found && found.length > 0 && (
            <div className="mt-1.5 overflow-hidden rounded-[10px] border border-line bg-card shadow-lg">
              <Group title="Celá firma" suggestions={found} hint="Celá firma · všechny pobočky společně" onChoose={(suggestion) => setChoice({ suggestion, company: true })} />
              <Group title="Jedna pobočka" suggestions={found} hint="Jen tato pobočka" onChoose={(suggestion) => setChoice({ suggestion, company: false })} />
            </div>
          )}
          <p className="mt-2 text-sm text-muted">Návrhy pocházejí z Google Places. Vaše volba určí, zda se analyzuje celý řetězec, nebo jedna pobočka.</p>
        </div>
        <p className="text-sm text-muted">Zdroje: Google Maps, Firmy.cz</p>
      </main>
    </>
  );
}

function Group({ title, suggestions, hint, onChoose }: { title: string; suggestions: Suggestion[]; hint: string; onChoose: (suggestion: Suggestion) => void }) {
  return (
    <div role="group" aria-label={title}>
      <p aria-hidden="true" className="bg-page px-4 py-2 text-xs font-semibold tracking-wide text-muted uppercase">
        {title}
      </p>
      <ul>
        {suggestions.map((suggestion) => (
          <li key={suggestion.place_id} className="border-t border-line first:border-t-0">
            <button type="button" onClick={() => onChoose(suggestion)} className="block min-h-14 w-full px-4 py-2 text-left hover:bg-[#eef3fd]">
              <span className="block text-[15px] font-semibold">{suggestion.text}</span>
              <span className="block text-sm text-muted">{hint}</span>
            </button>
          </li>
        ))}
      </ul>
    </div>
  );
}
