import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { ApiError } from "../api/client";
import { ApiProvider } from "../api/context";
import { fakeApi, fakeResult } from "../fakeApi";
import { ResultScreen } from "./ResultScreen";

function setup(api: ReturnType<typeof fakeApi>) {
  return render(
    <ApiProvider api={api}>
      <MemoryRouter initialEntries={["/runs/run-1/result"]}>
        <Routes>
          <Route path="/runs/:id/result" element={<ResultScreen />} />
          <Route path="/runs/:id" element={<p>progress</p>} />
          <Route path="/" element={<p>search</p>} />
        </Routes>
      </MemoryRouter>
    </ApiProvider>,
  );
}

it("reads the result of the Run it was opened with and names the Company", async () => {
  const api = fakeApi();
  setup(api);
  expect(await screen.findByRole("heading", { level: 1, name: "Kavárna U Mlýna" })).toBeInTheDocument();
  expect(api.runResult).toHaveBeenCalledWith("run-1");
  expect(screen.getByRole("link", { name: "Nové hledání" })).toHaveAttribute("href", "/");
});

it("says the Run does not exist on a 404", async () => {
  setup(fakeApi({ runResult: vi.fn(async () => Promise.reject(new ApiError(404))) }));
  expect(await screen.findByRole("alert")).toHaveTextContent("Tato analýza neexistuje.");
});

it("sends the user back to the progress when the Run is not finished (409)", async () => {
  setup(fakeApi({ runResult: vi.fn(async () => Promise.reject(new ApiError(409))) }));
  expect(await screen.findByRole("alert")).toHaveTextContent("ještě neskončila");
  expect(screen.getByRole("link", { name: "Zobrazit průběh" })).toHaveAttribute("href", "/runs/run-1");
});

it("explains a failed call with the shared wording", async () => {
  setup(fakeApi({ runResult: vi.fn(async () => Promise.reject(new ApiError(429))) }));
  expect(await screen.findByRole("alert")).toHaveTextContent("limitu");
});

const twoSources = () =>
  fakeResult({
    company: {
      name: "Kavárna U Mlýna",
      industry: "cafe",
      places: [
        { source: "google_maps", external_id: "g1", name: "Kavárna Vinohrady", address: "Praha 2" },
        { source: "firmy_cz", external_id: "f1", name: "Kavárna Smíchov", address: "Praha 5" },
      ],
    },
    metrics: {
      trend: [
        { source: "google_maps", period_start: "2025-06-01", average_rating: 4.0, count: 10, sentiment: 0 },
        { source: "google_maps", period_start: "2026-06-01", average_rating: 4.6, count: 10, sentiment: 0 },
        { source: "firmy_cz", period_start: "2026-06-01", average_rating: 4.0, count: 10, sentiment: 0 },
      ],
      topic_shares: [],
      changes: [],
      overall: { average_rating: 3.9, count: 40 },
      per_source: [
        { source: "google_maps", summary: { average_rating: 4.4, count: 30 } },
        { source: "firmy_cz", summary: { average_rating: 2.5, count: 10 } },
      ],
      per_place: [
        { source: "google_maps", place_external_id: "g1", summary: { average_rating: 4.4, count: 30 } },
        { source: "firmy_cz", place_external_id: "f1", summary: { average_rating: 2.5, count: 10 } },
      ],
    },
    cost: "1.5",
  });

it("shows the overall rating, its change against the previous 12 months, per Source cards and the cost", async () => {
  setup(fakeApi({ runResult: vi.fn(async () => twoSources()) }));
  const overall = await screen.findByRole("group", { name: "Celkové hodnocení" });
  expect(within(overall).getByText("3,9")).toBeInTheDocument();
  expect(within(overall).getByText("40 recenzí")).toBeInTheDocument();
  expect(within(overall).getByText(/\+0,3 oproti předchozím 12 měsícům/)).toBeInTheDocument();
  const google = screen.getByRole("group", { name: "Google Maps" });
  expect(within(google).getByText("4,4")).toBeInTheDocument();
  expect(within(google).getByText("30 recenzí")).toBeInTheDocument();
  expect(within(google).getByText("75 %")).toBeInTheDocument();
  const firmy = screen.getByRole("group", { name: "Firmy.cz" });
  expect(within(firmy).getByText("2,5")).toBeInTheDocument();
  expect(within(firmy).getByText("25 %")).toBeInTheDocument();
  expect(within(screen.getByRole("group", { name: "Náklady analýzy" })).getByText("1.50 USD")).toBeInTheDocument();
});

it("shows no change when there is nothing to compare with", async () => {
  setup(fakeApi());
  const overall = await screen.findByRole("group", { name: "Celkové hodnocení" });
  expect(within(overall).queryByText(/oproti/)).not.toBeInTheDocument();
});

it("shows a dash when no Review was found", async () => {
  const empty = fakeResult({ metrics: { ...fakeResult().metrics, trend: [], overall: null, per_source: [], per_place: [] }, reviews: 0 });
  setup(fakeApi({ runResult: vi.fn(async () => empty) }));
  const overall = await screen.findByRole("group", { name: "Celkové hodnocení" });
  expect(within(overall).getByText("–")).toBeInTheDocument();
});

it("narrows the cards to one Place when its tab is chosen", async () => {
  const user = userEvent.setup();
  setup(fakeApi({ runResult: vi.fn(async () => twoSources()) }));
  const tabs = await screen.findAllByRole("tab");
  expect(tabs.map((tab) => tab.textContent)).toEqual(["Celá firma", "Kavárna Vinohrady · Google Maps", "Kavárna Smíchov · Firmy.cz"]);
  expect(tabs[0]).toHaveAttribute("aria-selected", "true");
  await user.click(tabs[2]!);
  expect(tabs[2]).toHaveAttribute("aria-selected", "true");
  const overall = screen.getByRole("group", { name: "Celkové hodnocení" });
  expect(within(overall).getByText("2,5")).toBeInTheDocument();
  expect(screen.queryByRole("group", { name: "Google Maps" })).not.toBeInTheDocument();
  expect(screen.getByRole("group", { name: "Firmy.cz" })).toBeInTheDocument();
});
