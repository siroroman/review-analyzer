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
      rating_counts: [
        { stars: 5, count: 20 },
        { stars: 4, count: 10 },
        { stars: 3, count: 4 },
        { stars: 2, count: 3 },
        { stars: 1, count: 3 },
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

it("calls out a drop on the chart with its month, size and main Topic", async () => {
  const withDrop = fakeResult({
    topics: [{ key: "service", name: "Obsluha" }],
    metrics: {
      ...fakeResult().metrics,
      changes: [
        {
          kind: "drop",
          source: "google_maps",
          period_start: "2026-02-01",
          delta: -1,
          main_topic_key: "service",
        },
      ],
    },
  });
  setup(fakeApi({ runResult: vi.fn(async () => withDrop) }));
  await screen.findByRole("list", { name: "Poklesy a vzestupy" });
  expect(screen.getByText("▼ Únor: pokles o 1,0")).toBeInTheDocument();
  expect(screen.getByText("Hlavní téma: Obsluha")).toBeInTheDocument();
});

it("calls out a drop without a main Topic with the first line only", async () => {
  const withDrop = fakeResult({
    metrics: {
      ...fakeResult().metrics,
      changes: [
        {
          kind: "drop",
          source: "google_maps",
          period_start: "2026-02-01",
          delta: -1,
          main_topic_key: null,
        },
      ],
    },
  });
  setup(fakeApi({ runResult: vi.fn(async () => withDrop) }));
  expect(await screen.findByText("▼ Únor: pokles o 1,0")).toBeInTheDocument();
  expect(screen.queryByText(/Hlavní téma/)).not.toBeInTheDocument();
});

it("marks a rise on the chart with its month", async () => {
  const withRise = fakeResult({
    metrics: {
      ...fakeResult().metrics,
      changes: [
        {
          kind: "rise",
          source: "google_maps",
          period_start: "2026-01-01",
          delta: 0.7,
          main_topic_key: null,
        },
      ],
    },
  });
  setup(fakeApi({ runResult: vi.fn(async () => withRise) }));
  expect(await screen.findByText("▲ Leden: oživení")).toBeInTheDocument();
});

it("has a legend with a solid line for Google Maps and a dashed one for Firmy.cz", async () => {
  setup(fakeApi({ runResult: vi.fn(async () => twoSources()) }));
  const legend = await screen.findByRole("list", { name: "Legenda grafu" });
  const [google, firmy] = within(legend).getAllByRole("listitem");
  expect(google).toHaveTextContent("Google Maps");
  expect(google!.querySelector("line")).not.toHaveAttribute("stroke-dasharray");
  expect(firmy).toHaveTextContent("Firmy.cz");
  expect(firmy!.querySelector("line")).toHaveAttribute("stroke-dasharray");
});

it("fits the rating axis to the data in half-star steps", async () => {
  const { container } = setup(fakeApi());
  await screen.findByRole("img", { name: /Vývoj hodnocení/ });
  const ticks = [...container.querySelectorAll(".recharts-yAxis-tick-labels text")].map((tick) => tick.textContent);
  expect(ticks).toEqual(["3,0", "3,5", "4,0", "4,5", "5,0"]);
});

it("explains under the chart what the marked months are", async () => {
  setup(fakeApi());
  expect(await screen.findByText(/Zvýrazněný měsíc je pokles/)).toBeInTheDocument();
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

it("shows the shared header with the cache note and a Nové hledání button once the result is there", async () => {
  setup(fakeApi());
  const header = await screen.findByRole("banner");
  expect(within(header).getByText("Analýza dokončena · výsledek v cache 24 h")).toBeInTheDocument();
  const link = within(header).getByRole("link", { name: "Nové hledání" });
  expect(link).toHaveAttribute("href", "/");
  expect(link).toHaveClass("min-h-11");
});

it("keeps the way to a new search when the result cannot be loaded", async () => {
  setup(
    fakeApi({
      runResult: vi.fn(async () => Promise.reject(new ApiError(404))),
    }),
  );
  await screen.findByRole("alert");
  expect(
    within(screen.getByRole("banner")).getByRole("link", {
      name: "Nové hledání",
    }),
  ).toBeInTheDocument();
  expect(screen.queryByText(/výsledek v cache/)).not.toBeInTheDocument();
});

it("says under the title which Sources and period the result covers", async () => {
  setup(fakeApi());
  expect(await screen.findByText("Google Maps · recenze za posledních 12 měsíců")).toBeInTheDocument();
});

it("lists every Source of the Company in the sub-line", async () => {
  setup(fakeApi({ runResult: vi.fn(async () => twoSources()) }));
  expect(await screen.findByText("Google Maps, Firmy.cz · recenze za posledních 12 měsíců")).toBeInTheDocument();
});

it("writes the overall rating out of 5 and marks a rise with an arrow as well as the sign", async () => {
  setup(fakeApi({ runResult: vi.fn(async () => twoSources()) }));
  const overall = await screen.findByRole("group", {
    name: "Celkové hodnocení",
  });
  expect(within(overall).getByText("/ 5 ·")).toBeInTheDocument();
  expect(within(overall).getByText(/\+0,3 oproti předchozím 12 měsícům/)).toHaveTextContent("▲");
});

it("marks a fall against the previous 12 months with a down arrow", async () => {
  const falling = fakeResult({
    metrics: {
      ...fakeResult().metrics,
      trend: [
        {
          source: "google_maps",
          period_start: "2025-06-01",
          average_rating: 4.5,
          count: 10,
          sentiment: 0,
        },
        {
          source: "google_maps",
          period_start: "2026-06-01",
          average_rating: 4.4,
          count: 10,
          sentiment: 0,
        },
      ],
    },
  });
  setup(fakeApi({ runResult: vi.fn(async () => falling) }));
  const overall = await screen.findByRole("group", {
    name: "Celkové hodnocení",
  });
  expect(within(overall).getByText(/−0,1 oproti předchozím 12 měsícům/)).toHaveTextContent("▼");
});

it("shows how many suspicious Reviews were left out of the analysis", async () => {
  setup(fakeApi({ runResult: vi.fn(async () => fakeResult({ flagged: 7 })) }));
  const card = await screen.findByRole("group", { name: "Podezřelé recenze" });
  expect(within(card).getByText("7")).toBeInTheDocument();
  expect(within(card).getByText("vyřazeno z analýzy")).toBeInTheDocument();
});

it("shows the suspicious Reviews card with a zero when none were flagged", async () => {
  setup(fakeApi());
  const card = await screen.findByRole("group", { name: "Podezřelé recenze" });
  expect(within(card).getByText("0")).toBeInTheDocument();
});

it("shows the rating distribution from 5 to 1 stars with count and percent", async () => {
  setup(fakeApi());
  const card = await screen.findByRole("group", {
    name: "Rozdělení hodnocení",
  });
  expect(within(card).getByText("Všech 18 recenzí")).toBeInTheDocument();
  const rows = within(card).getAllByRole("button");
  expect(rows.map((row) => row.textContent)).toEqual(["5 ★8 · 44 %", "4 ★6 · 33 %", "3 ★2 · 11 %", "2 ★1 · 6 %", "1 ★1 · 6 %"]);
  expect(rows[0]).toHaveAccessibleName("5 ★, 8 recenzí, 44 %");
  rows.forEach((row) => expect(row).toHaveClass("min-h-11"));
});

it("says how many Reviews have 4 or 5 stars", async () => {
  setup(fakeApi());
  expect(await screen.findByText(/78 % recenzí má 4 nebo 5 hvězdiček/)).toBeInTheDocument();
});

it("lists the Reviews with a rating in the side panel when its row is clicked", async () => {
  const user = userEvent.setup();
  const reviews = vi.fn(async () => [
    {
      id: "r1",
      source: "google_maps" as const,
      place_name: "Kavárna",
      rating: 1,
      date: "2026-02-03",
      text: "Špatné.",
    },
  ]);
  setup(fakeApi({ reviews }));
  await user.click(await screen.findByRole("button", { name: /^1 ★/ }));
  expect(reviews).toHaveBeenCalledWith("run-1", { rating: 1 });
  const panel = await screen.findByRole("dialog", { name: "Recenze: 1 ★" });
  expect(await within(panel).findByText("Špatné.")).toBeInTheDocument();
});

it("leaves the distribution out when there are no Reviews", async () => {
  const empty = fakeResult({
    metrics: {
      ...fakeResult().metrics,
      trend: [],
      overall: null,
      per_source: [],
      per_place: [],
      rating_counts: [],
    },
    reviews: 0,
  });
  setup(fakeApi({ runResult: vi.fn(async () => empty) }));
  await screen.findByRole("heading", { level: 1 });
  expect(screen.queryByRole("group", { name: "Rozdělení hodnocení" })).not.toBeInTheDocument();
});

it("keeps the distribution on the whole Company when a Place tab is chosen", async () => {
  const user = userEvent.setup();
  setup(fakeApi({ runResult: vi.fn(async () => twoSources()) }));
  await user.click((await screen.findAllByRole("tab"))[1]!);
  expect(screen.getByText("Rozdělení ukazuje celou firmu.")).toBeInTheDocument();
});
