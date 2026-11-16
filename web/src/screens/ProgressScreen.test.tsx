import { act, render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { ApiError, type RunProgress } from "../api/client";
import { ApiProvider } from "../api/context";
import { fakeApi } from "../fakeApi";
import { ProgressScreen } from "./ProgressScreen";

const at = (status: RunProgress["status"], cost: string, finished = false): RunProgress => ({
  run_id: "run-1",
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
  expect(screen.getByText(/0\.123 USD/)).toBeInTheDocument();
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
  expect(screen.getByText(/0\.200 USD/)).toBeInTheDocument();
  await tick(2000);
  expect(runProgress).toHaveBeenCalledTimes(3);
  expect(screen.getByText(/0\.300 USD/)).toBeInTheDocument();
});

it("stops polling when the Run is done", async () => {
  const runProgress = vi.fn(async () => at("done", "0.5", true));
  setup(fakeApi({ runProgress }));
  await tick(0);
  await tick(10000);
  expect(runProgress).toHaveBeenCalledTimes(1);
  expect(screen.getByRole("status")).toHaveTextContent(/hotovo/i);
});

it.each([
  ["partial", /částečný/i],
  ["failed", /selhala/i],
] as const)("says how a %s Run ended and stops", async (status, text) => {
  const runProgress = vi.fn(async () => at(status, "0.5", true));
  setup(fakeApi({ runProgress }));
  await tick(0);
  await tick(6000);
  expect(runProgress).toHaveBeenCalledTimes(1);
  expect(screen.getByRole("status")).toHaveTextContent(text);
});

it.each(["done", "partial"] as const)("links a %s Run to its result", async (status) => {
  setup(fakeApi({ runProgress: vi.fn(async () => at(status, "0.5", true)) }));
  await tick(0);
  expect(screen.getByRole("link", { name: "Zobrazit výsledek" })).toHaveAttribute("href", "/runs/run-1/result");
});

it("offers no result link for a failed Run", async () => {
  setup(fakeApi({ runProgress: vi.fn(async () => at("failed", "0.5", true)) }));
  await tick(0);
  expect(screen.queryByRole("link", { name: "Zobrazit výsledek" })).not.toBeInTheDocument();
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
  expect(screen.getByText(/0\.100 USD/)).toBeInTheDocument();
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
  expect(screen.getByText(/0\.560 USD/)).toBeInTheDocument();
  expect(screen.getByText(/částečný výsledek/i)).toBeInTheDocument();
  expect(screen.queryByRole("progressbar")).not.toBeInTheDocument();
  expect(screen.queryByText(/rozpočtu \d/)).not.toBeInTheDocument();
});
