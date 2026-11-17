import createClient from "openapi-fetch";
import type { components, paths } from "./schema";

export type Suggestion = components["schemas"]["SuggestionOut"];
export type Branch = components["schemas"]["BranchOut"];
export type RunIn = components["schemas"]["RunIn"];
export type RunOut = components["schemas"]["RunOut"];
export type RunProgress = components["schemas"]["StatusOut"];
export type Metrics = components["schemas"]["Metrics"];
export type RunResult = components["schemas"]["ResultOut"];

/** One Review as the side panel shows it. */
export interface ReviewView {
  id: string;
  source: "google_maps" | "firmy_cz";
  place_name: string;
  rating: number;
  /** ISO date. */
  date: string;
  text: string;
}
/** Which Reviews of a Run to read: the ones an insight cites, the ones mentioning a Topic, or the ones with a star rating. */
export type ReviewQuery = { ids: string[] } | { topic: string } | { rating: number };
export type RunStatus = RunProgress["status"];

/** An answer that is not a success. `status` is the HTTP status, or 0 when the server was not reached. */
export class ApiError extends Error {
  constructor(readonly status: number) {
    super(`API error ${status}`);
  }
}

/** The API as the screens see it; tests put a fake in its place. */
export interface Api {
  suggest(query: string, signal?: AbortSignal): Promise<Suggestion[]>;
  branches(placeId: string): Promise<Branch[]>;
  startRun(input: RunIn): Promise<RunOut>;
  runProgress(runId: string): Promise<RunProgress>;
  runResult(runId: string): Promise<RunResult>;
  reviews(runId: string, query: ReviewQuery): Promise<ReviewView[]>;
}

export function createApi(token: string, baseUrl = import.meta.env.VITE_API_URL ?? "/api"): Api {
  const client = createClient<paths>({ baseUrl, headers: { Authorization: `Bearer ${token}` } });

  async function call<T>(request: Promise<{ data?: T; response: Response }>): Promise<T> {
    let result;
    try {
      result = await request;
    } catch (error) {
      if (error instanceof DOMException && error.name === "AbortError") throw error;
      throw new ApiError(0);
    }
    if (result.data === undefined) throw new ApiError(result.response.status);
    return result.data;
  }

  return {
    suggest: (query, signal) => call(client.GET("/places/suggest", { params: { query: { q: query } }, signal })),
    branches: (placeId) => call(client.GET("/places/{place_id}/branches", { params: { path: { place_id: placeId } } })),
    startRun: (input) => call(client.POST("/runs", { body: input })),
    runProgress: (runId) => call(client.GET("/runs/{run_id}", { params: { path: { run_id: runId } } })),
    runResult: (runId) => call(client.GET("/runs/{run_id}/result", { params: { path: { run_id: runId } } })) ,
    reviews: (runId, query) => {
      // The API serves Reviews by ids or by Topic only; by star rating is not there yet, so the panel shows its error state.
      if ("rating" in query) return Promise.reject(new ApiError(501));
      const params = { path: { run_id: runId }, query: "ids" in query ? { ids: query.ids } : { topic: query.topic } };
      return call(client.GET("/runs/{run_id}/reviews", { params }));
    },
  };
}
