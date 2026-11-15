import { useEffect, useState } from "react";
import { useApi } from "../api/context";
import type { Suggestion } from "../api/client";
import { useDebounced } from "../useDebounced";
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
    <main className="mx-auto max-w-xl p-6">
      <h1 className="mb-4 text-2xl font-semibold">Analýza recenzí firmy</h1>
      <input
        type="search"
        role="searchbox"
        aria-label="Název firmy nebo pobočky"
        placeholder="Název firmy nebo pobočky"
        value={text}
        onChange={(event) => setText(event.target.value)}
        className="w-full rounded border p-2"
      />
      {problem && (
        <p role="alert" className="mt-3 rounded bg-red-50 p-3 text-red-800">
          {problem}
        </p>
      )}
      {found?.length === 0 && <p className="mt-3 text-gray-600">Nic jsme nenašli.</p>}
      <ul className="mt-3 space-y-2">
        {found?.map((suggestion) => (
          <li key={suggestion.place_id} className="rounded border p-3">
            <p className="mb-2">{suggestion.text}</p>
            <div className="flex gap-2">
              <button type="button" className="rounded border px-3 py-1" onClick={() => setChoice({ suggestion, company: false })}>
                Jen tato pobočka
              </button>
              <button type="button" className="rounded border px-3 py-1" onClick={() => setChoice({ suggestion, company: true })}>
                Celá firma
              </button>
            </div>
          </li>
        ))}
      </ul>
    </main>
  );
}
