import { act, render, screen } from "@testing-library/react";
import { MemoryRouter, Route, RouterProvider, Routes, createMemoryRouter } from "react-router-dom";
import { ApiError, type RunProgress } from "../api/client";
import { ApiProvider } from "../api/context";
import { fakeApi } from "../fakeApi";
import { ProgressScreen } from "./ProgressScreen";

const at = (status: RunProgress["status"], cost: string, finished = false): RunProgress => ({
  run_id: "run-1",
  company_name: "Kavárna",
  status,
  finished,
  cost,
  budget: "1",
  downloaded: null,
  flagged: null,
  classified: null,
  to_classify: null,
  step_cost: { downloading: null, classifying: null, analysis: null },
});

function setup(api: ReturnType<typeof fakeApi>) {
  vi.useFakeTimers();
  return render(
    <ApiProvider api={api}>
      <MemoryRouter initialEntries={["/runs/run-1"]}>
        <Routes>
          <Route path="/runs/:id" element={<ProgressScreen />} />
          <Route path="/runs/:id/result" element={<p>the result</p>} />
          <Route path="/" element={<p>search</p>} />
        </Routes>
      </MemoryRouter>
    </ApiProvider>,
  );
}

const tick = (ms: number) => act(() => vi.advanceTimersByTimeAsync(ms));

afterEach(() => vi.useRealTimers());

it("shows the current step and the running cost at once, and reads the Run it was opened with", async () => {
  const api = fakeApi({ runProgress: vi.fn(async () => at("classifying", "0.1234")) });
  setup(api);
  await tick(0);
  expect(api.runProgress).toHaveBeenCalledWith("run-1");
  expect(screen.getByText("Třídění recenzí do témat").closest("li")).toHaveAttribute("aria-current", "step");
  expect(screen.getByText("Stahování recenzí").closest("li")).toHaveAttribute("data-state", "done");
  expect(screen.getByText("Analýza a doporučení").closest("li")).toHaveAttribute("data-state", "todo");
  expect(screen.getByText(/0,12 USD/)).toBeInTheDocument();
});

it("polls every 2 seconds and shows the cost growing", async () => {
  const runProgress = vi
    .fn()
    .mockResolvedValueOnce(at("downloading", "0.1"))
    .mockResolvedValueOnce(at("downloading", "0.2"))
    .mockResolvedValue(at("classifying", "0.3"));
  setup(fakeApi({ runProgress }));
  await tick(0);
  expect(runProgress).toHaveBeenCalledTimes(1);
  await tick(1999);
  expect(runProgress).toHaveBeenCalledTimes(1);
  await tick(1);
  expect(runProgress).toHaveBeenCalledTimes(2);
  expect(screen.getByText(/0,20 USD/)).toBeInTheDocument();
  await tick(2000);
  expect(runProgress).toHaveBeenCalledTimes(3);
  expect(screen.getByText(/0,30 USD/)).toBeInTheDocument();
});

it.each(["done", "partial"] as const)("opens the result as soon as a Run turns %s, and stops polling", async (status) => {
  const runProgress = vi
    .fn()
    .mockResolvedValueOnce(at("classifying", "0.1"))
    .mockResolvedValue(at(status, "0.5", true));
  setup(fakeApi({ runProgress }));
  await tick(0);
  expect(screen.queryByText("the result")).not.toBeInTheDocument();
  await tick(2000);
  expect(screen.getByText("the result")).toBeInTheDocument();
  await tick(10000);
  expect(runProgress).toHaveBeenCalledTimes(2);
});

it("goes straight to the result when the link of a finished Run is opened", async () => {
  setup(fakeApi({ runProgress: vi.fn(async () => at("done", "0.5", true)) }));
  await tick(0);
  expect(screen.getByText("the result")).toBeInTheDocument();
});

it("replaces the progress page, so Back does not return to a finished Run", async () => {
  const router = createMemoryRouter(
    [
      { path: "/", element: <p>search</p> },
      { path: "/runs/:id", element: <ProgressScreen /> },
      { path: "/runs/:id/result", element: <p>the result</p> },
    ],
    { initialEntries: ["/", "/runs/run-1"], initialIndex: 1 },
  );
  vi.useFakeTimers();
  render(
    <ApiProvider api={fakeApi({ runProgress: vi.fn(async () => at("done", "0.5", true)) })}>
      <RouterProvider router={router} />
    </ApiProvider>,
  );
  await tick(0);
  expect(screen.getByText("the result")).toBeInTheDocument();
  await act(() => router.navigate(-1));
  expect(screen.getByText("search")).toBeInTheDocument();
});

it("keeps a failed Run on the page with its message and a way to a new search", async () => {
  const runProgress = vi.fn(async () => at("failed", "0.5", true));
  setup(fakeApi({ runProgress }));
  await tick(0);
  await tick(6000);
  expect(runProgress).toHaveBeenCalledTimes(1);
  expect(screen.getByRole("status")).toHaveTextContent(/selhala/i);
  expect(screen.queryByRole("link", { name: "Zobrazit výsledek" })).not.toBeInTheDocument();
  expect(screen.getByRole("link", { name: "Nové hledání" })).toHaveAttribute("href", "/");
});

it("says 429 means too many requests and keeps polling", async () => {
  const runProgress = vi
    .fn()
    .mockRejectedValueOnce(new ApiError(429))
    .mockResolvedValue(at("downloading", "0.1"));
  setup(fakeApi({ runProgress }));
  await tick(0);
  expect(screen.getByRole("alert")).toHaveTextContent(/příliš mnoho požadavků/i);
  expect(screen.queryByRole("link", { name: "Nové hledání" })).not.toBeInTheDocument();
  await tick(2000);
  expect(screen.queryByRole("alert")).not.toBeInTheDocument();
});

it("says a server error is on our side and keeps polling", async () => {
  const runProgress = vi
    .fn()
    .mockRejectedValueOnce(new ApiError(503))
    .mockResolvedValue(at("downloading", "0.1"));
  setup(fakeApi({ runProgress }));
  await tick(0);
  expect(screen.getByRole("alert")).toHaveTextContent(/chyba na straně serveru/i);
  await tick(2000);
  expect(runProgress).toHaveBeenCalledTimes(2);
  expect(screen.queryByRole("alert")).not.toBeInTheDocument();
});

it("says a Run does not exist and stops", async () => {
  const runProgress = vi.fn(async () => Promise.reject(new ApiError(404)));
  setup(fakeApi({ runProgress }));
  await tick(0);
  await tick(6000);
  expect(runProgress).toHaveBeenCalledTimes(1);
  expect(screen.getByRole("alert")).toHaveTextContent(/neexistuje/i);
});

it("explains a wrong Demo token and stops", async () => {
  const runProgress = vi.fn(async () => Promise.reject(new ApiError(401)));
  setup(fakeApi({ runProgress }));
  await tick(0);
  await tick(6000);
  expect(runProgress).toHaveBeenCalledTimes(1);
  expect(screen.getByRole("alert")).toHaveTextContent(/odkaz/i);
});

it("keeps trying after a network error and recovers", async () => {
  const runProgress = vi
    .fn()
    .mockRejectedValueOnce(new ApiError(0))
    .mockResolvedValue(at("downloading", "0.1"));
  setup(fakeApi({ runProgress }));
  await tick(0);
  expect(screen.getByRole("alert")).toHaveTextContent(/spojení/i);
  await tick(2000);
  expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  expect(screen.getByText(/0,10 USD/)).toBeInTheDocument();
});

it("stops polling when the screen closes", async () => {
  const runProgress = vi.fn(async () => at("downloading", "0.1"));
  const { unmount } = setup(fakeApi({ runProgress }));
  await tick(0);
  unmount();
  const calls = runProgress.mock.calls.length;
  await tick(6000);
  expect(runProgress.mock.calls.length).toBe(calls);
});

it("shows the app header and says each step in words, not by colour alone", async () => {
  setup(fakeApi({ runProgress: vi.fn(async () => at("classifying", "0.1234")) }));
  await tick(0);
  expect(screen.getByRole("banner")).toHaveTextContent("Review Analyzer");
  const card = (name: string) => screen.getByText(name).closest("li") as HTMLElement;
  expect(card("Stahování recenzí")).toHaveTextContent("Hotovo");
  expect(card("Třídění recenzí do témat")).toHaveTextContent("Probíhá");
  expect(card("Analýza a doporučení")).toHaveTextContent("Čeká");
  expect(screen.getAllByRole("listitem")).toHaveLength(3);
});

it("waits for every step while the Run is queued", async () => {
  setup(fakeApi({ runProgress: vi.fn(async () => at("queued", "0")) }));
  await tick(0);
  expect(screen.getAllByText("Čeká")).toHaveLength(3);
  expect(screen.getByText(/ve frontě/i)).toBeInTheDocument();
});

it("shows the running cost and the partial result note, and no budget the API did not send", async () => {
  setup(fakeApi({ runProgress: vi.fn(async () => at("classifying", "0.56")) }));
  await tick(0);
  expect(screen.getByText(/0,56 USD/)).toBeInTheDocument();
  expect(screen.getByText(/částečný výsledek/i)).toBeInTheDocument();
  expect(screen.queryByRole("progressbar")).not.toBeInTheDocument();
  expect(screen.queryByText(/rozpočtu \d/)).not.toBeInTheDocument();
});

const withDetails = (status: RunProgress["status"], extra: Partial<RunProgress>): RunProgress => ({ ...at(status, "0.56"), ...extra });
const row = (name: string) => screen.getByText(name).closest("li") as HTMLElement;

it("shows the cost of each step: done with a check mark, running as running, waiting without cost", async () => {
  const step_cost = { downloading: "0.35", classifying: "0.21", analysis: null };
  setup(fakeApi({ runProgress: vi.fn(async () => withDetails("classifying", { step_cost })) }));
  await tick(0);
  expect(row("Stahování recenzí")).toHaveTextContent("Hotovo · 0,35 USD");
  expect(row("Stahování recenzí")).toHaveTextContent("✓");
  expect(row("Třídění recenzí do témat")).toHaveTextContent("Probíhá · 0,21 USD");
  expect(row("Analýza a doporučení")).toHaveTextContent(/^.*Čeká$/);
  expect(row("Analýza a doporučení")).toHaveTextContent("Trendy, poklesy, shrnutí");
});

it("shows the running step as a spinning ring that stands still under reduced motion, with the word Probíhá", async () => {
  setup(fakeApi({ runProgress: vi.fn(async () => at("downloading", "0.1")) }));
  await tick(0);
  const ring = row("Stahování recenzí").querySelector('[data-ring="active"]');
  expect(ring).not.toBeNull();
  expect(ring).toHaveClass("motion-safe:animate-spin");
  expect(ring).not.toHaveClass("animate-spin");
  expect(row("Stahování recenzí")).toHaveTextContent("Probíhá");
});

it("shows the count of downloaded Reviews per Source", async () => {
  const downloaded = { google_maps: 1204, firmy_cz: 980 };
  setup(fakeApi({ runProgress: vi.fn(async () => withDetails("downloading", { downloaded })) }));
  await tick(0);
  expect(row("Stahování recenzí")).toHaveTextContent("Google Maps 1 204 · Firmy.cz 980");
});
