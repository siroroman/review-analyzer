import { ApiError, createApi } from "./client";

function respond(body: unknown, status = 200) {
  const fetchMock = vi.fn(async (_request: Request) => new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } }));
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

afterEach(() => vi.unstubAllGlobals());

const sent = (mock: ReturnType<typeof respond>) => mock.mock.calls[0]![0] as unknown as Request;

it("sends the Demo token and the typed query", async () => {
  const fetchMock = respond([{ place_id: "g1", text: "Kavárna" }]);
  const found = await createApi("tok", "http://api").suggest("kav");
  expect(found).toEqual([{ place_id: "g1", text: "Kavárna" }]);
  expect(sent(fetchMock).url).toBe("http://api/places/suggest?q=kav");
  expect(sent(fetchMock).headers.get("Authorization")).toBe("Bearer tok");
});

it("asks for the branches of a Place", async () => {
  const fetchMock = respond([]);
  await createApi("tok", "http://api").branches("g1");
  expect(sent(fetchMock).url).toBe("http://api/places/g1/branches");
});

it("starts a Run with a body", async () => {
  const fetchMock = respond({ run_id: "r1", status: "queued", reused: false }, 202);
  const run = await createApi("tok", "http://api").startRun({ place_ids: ["g1"], name: "K", industry: "cafe" });
  expect(run.run_id).toBe("r1");
  expect(sent(fetchMock).method).toBe("POST");
  expect(await sent(fetchMock).json()).toEqual({ place_ids: ["g1"], name: "K", industry: "cafe" });
});

it("reads the progress of a Run", async () => {
  const fetchMock = respond({ run_id: "r1", status: "queued", finished: false, cost: "0" });
  expect((await createApi("tok", "http://api").runProgress("r1")).cost).toBe("0");
  expect(sent(fetchMock).url).toBe("http://api/runs/r1");
});

it("turns an error answer into an ApiError with its status", async () => {
  respond({ detail: "unauthorized" }, 401);
  await expect(createApi("bad", "http://api").runProgress("r1")).rejects.toMatchObject({ status: 401 });
});

it("turns an unreachable server into an ApiError with status 0", async () => {
  vi.stubGlobal("fetch", vi.fn(async () => Promise.reject(new TypeError("offline"))));
  await expect(createApi("tok", "http://api").runProgress("r1")).rejects.toEqual(new ApiError(0));
});

it("lets an abort through as an abort", async () => {
  vi.stubGlobal("fetch", vi.fn(async () => Promise.reject(new DOMException("aborted", "AbortError"))));
  await expect(createApi("tok", "http://api").suggest("k")).rejects.toMatchObject({ name: "AbortError" });
});
