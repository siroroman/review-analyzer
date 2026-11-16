import { useEffect, useRef, useState } from "react";
import type { ReviewView } from "../api/client";
import { describeError } from "./errors";
import { SOURCE_LABEL } from "./result";

/** What the panel shows: a title and how to load its Reviews. */
export interface PanelRequest {
  title: string;
  load: () => Promise<ReviewView[]>;
}

/** A side panel with the Reviews a Topic or an insight cites. Escape and the button close it and hand the focus back. */
export function ReviewsPanel({ request, onClose }: { request: PanelRequest; onClose: () => void }) {
  const [reviews, setReviews] = useState<ReviewView[] | null>(null);
  const [error, setError] = useState<unknown>(null);
  const closeButton = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    const opener = document.activeElement;
    closeButton.current?.focus();
    return () => {
      if (opener instanceof HTMLElement && opener.isConnected) opener.focus();
    };
  }, []);

  useEffect(() => {
    let stopped = false;
    setReviews(null);
    setError(null);
    request.load().then(
      (loaded) => !stopped && setReviews(loaded),
      (failed) => !stopped && setError(failed),
    );
    return () => {
      stopped = true;
    };
  }, [request]);

  return (
    <aside
      role="dialog"
      aria-label={request.title}
      onKeyDown={(event) => event.key === "Escape" && onClose()}
      className="fixed inset-y-0 right-0 z-10 flex w-full max-w-md flex-col gap-3 overflow-y-auto border-l border-line bg-card p-4 shadow-xl"
    >
      <div className="flex items-center justify-between gap-2">
        <h2 className="text-lg font-semibold">{request.title}</h2>
        <button ref={closeButton} onClick={onClose} className="min-h-11 rounded border border-line px-4">
          Zavřít
        </button>
      </div>
      {error !== null && (
        <p role="alert" className="rounded bg-red-50 p-3 text-red-800">
          {describeError(error, "načíst recenze")}
        </p>
      )}
      {error === null && reviews === null && <p className="text-muted">Načítám recenze…</p>}
      {reviews !== null && reviews.length === 0 && <p>Žádné recenze k zobrazení.</p>}
      <ul className="flex flex-col gap-3">
        {reviews?.map((review) => (
          <li key={review.id} className="rounded-card border border-line p-3">
            <p className="text-sm text-muted">
              {review.place_name} · {SOURCE_LABEL[review.source]} · {review.date}
            </p>
            <p className="font-semibold">{`${review.rating} / 5`}</p>
            <p>{review.text}</p>
          </li>
        ))}
      </ul>
    </aside>
  );
}
