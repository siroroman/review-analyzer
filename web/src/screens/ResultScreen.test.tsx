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

it("describes the timeline in words for a screen reader", async () => {
  setup(fakeApi());
  const chart = await screen.findByRole("img", { name: /Vývoj hodnocení/ });
  expect(chart).toHaveAccessibleName(expect.stringContaining("Google Maps: od 4,5 (01/2026) do 3,5 (02/2026)"));
});

it("lists a drop with the name of its main Topic and a rise, and marks nothing when there are no changes", async () => {
  const withChanges = fakeResult({
    topics: [{ key: "service", name: "Obsluha" }],
    metrics: {
      ...fakeResult().metrics,
      changes: [
        { kind: "drop", source: "google_maps", period_start: "2026-02-01", delta: -1, main_topic_key: "service" },
        { kind: "rise", source: "google_maps", period_start: "2026-03-01", delta: 0.7, main_topic_key: null },
      ],
    },
  });
  setup(fakeApi({ runResult: vi.fn(async () => withChanges) }));
  const list = await screen.findByRole("list", { name: "Poklesy a vzestupy" });
  const [drop, rise] = within(list).getAllByRole("listitem");
  expect(drop).toHaveTextContent("Pokles · Google Maps · 02/2026: −1,0 · hlavní téma: Obsluha");
  expect(drop).not.toHaveTextContent("service");
  expect(rise).toHaveTextContent("Vzestup · Google Maps · 03/2026: +0,7");
  expect(rise).not.toHaveTextContent("hlavní téma");
});

it("falls back to the Topic key when the result has no name for it", async () => {
  const unnamed = fakeResult({
    metrics: {
      ...fakeResult().metrics,
      changes: [{ kind: "drop", source: "google_maps", period_start: "2026-02-01", delta: -1, main_topic_key: "service" }],
    },
  });
  setup(fakeApi({ runResult: vi.fn(async () => unnamed) }));
  const list = await screen.findByRole("list", { name: "Poklesy a vzestupy" });
  expect(within(list).getByRole("listitem")).toHaveTextContent("hlavní téma: service");
});

it("names the main Topic of a drop in the callout on the chart", async () => {
  const withDrop = fakeResult({
    topics: [{ key: "service", name: "Obsluha" }],
    metrics: {
      ...fakeResult().metrics,
      changes: [{ kind: "drop", source: "google_maps", period_start: "2026-02-01", delta: -1, main_topic_key: "service" }],
    },
  });
  const { container } = setup(fakeApi({ runResult: vi.fn(async () => withDrop) }));
  await screen.findByRole("list", { name: "Poklesy a vzestupy" });
  expect(container.querySelector(".recharts-label")).toHaveTextContent("pokles + Obsluha");
});

it("shades the month of a drop with an area that has a width", async () => {
  const withDrop = fakeResult({
    metrics: {
      ...fakeResult().metrics,
      changes: [{ kind: "drop", source: "google_maps", period_start: "2026-02-01", delta: -1, main_topic_key: "service" }],
    },
  });
  const { container } = setup(fakeApi({ runResult: vi.fn(async () => withDrop) }));
  await screen.findByRole("list", { name: "Poklesy a vzestupy" });
  const area = container.querySelector(".recharts-reference-area-rect");
  expect(area).not.toBeNull();
  expect(Number(area!.getAttribute("width"))).toBeGreaterThan(0);
});

it("shows no list of changes when the Run found none", async () => {
  setup(fakeApi());
  await screen.findByRole("img", { name: /Vývoj hodnocení/ });
  expect(screen.queryByRole("list", { name: "Poklesy a vzestupy" })).not.toBeInTheDocument();
});

it("keeps the timeline on the whole Company when a Place tab is chosen", async () => {
  const user = userEvent.setup();
  setup(fakeApi());
  await user.click((await screen.findAllByRole("tab"))[1]!);
  expect(screen.getByText("Časová osa ukazuje celou firmu.")).toBeInTheDocument();
});

it("warns that a partial result shows only what was finished", async () => {
  setup(fakeApi({ runResult: vi.fn(async () => fakeResult({ status: "partial" })) }));
  expect(await screen.findByRole("status")).toHaveTextContent("Částečný výsledek");
});

it("says when the industry could not be inferred and generic topics were used", async () => {
  setup(fakeApi({ runResult: vi.fn(async () => fakeResult({ notes: ["industry_fallback"] })) }));
  expect(await screen.findByRole("status")).toHaveTextContent("Obor firmy se nepodařilo určit");
});

it("shows no banner for a complete result", async () => {
  setup(fakeApi());
  await screen.findByRole("heading", { level: 1 });
  expect(screen.queryByRole("status")).not.toBeInTheDocument();
});

it("says so instead of drawing an empty timeline when no Review was found", async () => {
  const empty = fakeResult({ metrics: { ...fakeResult().metrics, trend: [], overall: null, per_source: [], per_place: [] }, reviews: 0 });
  setup(fakeApi({ runResult: vi.fn(async () => empty) }));
  expect(await screen.findByText("Nenašli jsme žádné recenze, není co zobrazit.")).toBeInTheDocument();
  expect(screen.queryByRole("img", { name: /Vývoj hodnocení/ })).not.toBeInTheDocument();
});

it("explains that one month is too little to show a development", async () => {
  const single = fakeResult({ metrics: { ...fakeResult().metrics, trend: fakeResult().metrics.trend.slice(0, 1) } });
  setup(fakeApi({ runResult: vi.fn(async () => single) }));
  expect(await screen.findByText("Zatím je k dispozici jen jeden měsíc, vývoj nejde ukázat.")).toBeInTheDocument();
  expect(screen.getByRole("img", { name: /Vývoj hodnocení/ })).toBeInTheDocument();
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
