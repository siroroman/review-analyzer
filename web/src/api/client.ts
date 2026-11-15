import createClient from "openapi-fetch";
import type { components, paths } from "./schema";

export type Suggestion = components["schemas"]["SuggestionOut"];
export type Branch = components["schemas"]["BranchOut"];
export type RunIn = components["schemas"]["RunIn"];
export type RunOut = components["schemas"]["RunOut"];
export type RunProgress = components["schemas"]["StatusOut"];
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
  };
}
