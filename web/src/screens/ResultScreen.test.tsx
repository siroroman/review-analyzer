import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { ApiError, type RunResult } from "../api/client";
import { ApiProvider } from "../api/context";
import { fakeApi, fakeResult } from "../fakeApi";
import { readRecent } from "../recentRuns";
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

it("shows exactly two boxes: the rating of each Source and the cost", async () => {
  setup(fakeApi());
  const google = await screen.findByRole("group", { name: "Google Maps" });
  expect(within(google).getByText("4,4")).toBeInTheDocument();
  expect(within(google).getByText("18 recenzí")).toBeInTheDocument();
  expect(within(screen.getByRole("group", { name: "Náklady analýzy" })).getByText(/USD/)).toBeInTheDocument();
  expect(screen.getAllByRole("group").map((group) => group.getAttribute("aria-label")).filter((label) => label === "Google Maps" || label === "Náklady analýzy")).toEqual(["Google Maps", "Náklady analýzy"]);
  expect(screen.queryByRole("group", { name: "Celkové hodnocení" })).not.toBeInTheDocument();
  expect(screen.queryByRole("group", { name: "Podezřelé recenze" })).not.toBeInTheDocument();
});

it("keeps two boxes when the Company has two Sources: Google Maps and the cost", async () => {
  setup(fakeApi({ runResult: vi.fn(async () => twoSources()) }));
  const google = await screen.findByRole("group", { name: "Google Maps" });
  expect(within(google).getByText("4,4")).toBeInTheDocument();
  expect(screen.queryByRole("group", { name: "Firmy.cz" })).not.toBeInTheDocument();
  expect(screen.getByRole("group", { name: "Náklady analýzy" })).toBeInTheDocument();
});

it("has no buttons for the whole Company or a single Place", async () => {
  setup(fakeApi({ runResult: vi.fn(async () => twoSources()) }));
  await screen.findByRole("heading", { level: 1 });
  expect(screen.queryByRole("tab")).not.toBeInTheDocument();
  expect(screen.queryByRole("tablist")).not.toBeInTheDocument();
});

it("has no chart legend, no caption under the chart and no cost per service", async () => {
  setup(fakeApi());
  await screen.findByRole("img", { name: /Vývoj hodnocení/ });
  expect(screen.queryByRole("list", { name: "Legenda grafu" })).not.toBeInTheDocument();
  expect(screen.queryByText(/Zvýrazněný měsíc/)).not.toBeInTheDocument();
  expect(screen.queryByRole("group", { name: "Náklady podle služeb" })).not.toBeInTheDocument();
});

it("draws smooth lines without points", async () => {
  const three = fakeResult({
    metrics: {
      ...fakeResult().metrics,
      trend: [
        { source: "google_maps", period_start: "2026-01-01", average_rating: 4.5, count: 10, sentiment: 0 },
        { source: "google_maps", period_start: "2026-02-01", average_rating: 3.5, count: 8, sentiment: 0 },
        { source: "google_maps", period_start: "2026-03-01", average_rating: 4.2, count: 9, sentiment: 0 },
      ],
      changes: [],
    },
  });
  const { container } = setup(fakeApi({ runResult: vi.fn(async () => three) }));
  await screen.findByRole("img", { name: /Vývoj hodnocení/ });
  expect(container.querySelector(".recharts-line-dot")).toBeNull();
  expect(container.querySelector(".recharts-line-curve")!.getAttribute("d")).toMatch(/C/);
});

it("shows no Source box when no Review was found", async () => {
  const empty = fakeResult({ metrics: { ...fakeResult().metrics, trend: [], overall: null, per_source: [], per_place: [] }, reviews: 0 });
  setup(fakeApi({ runResult: vi.fn(async () => empty) }));
  expect(await screen.findByRole("group", { name: "Náklady analýzy" })).toBeInTheDocument();
  expect(screen.queryByRole("group", { name: "Google Maps" })).not.toBeInTheDocument();
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

it("fits the rating axis to the data in half-star steps", async () => {
  const { container } = setup(fakeApi());
  await screen.findByRole("img", { name: /Vývoj hodnocení/ });
  const ticks = [...container.querySelectorAll(".recharts-yAxis-tick-labels text")].map((tick) => tick.textContent);
  expect(ticks).toEqual(["3,0", "3,5", "4,0", "4,5", "5,0"]);
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

it("says under the title which Sources and months the result covers, not a fixed year", async () => {
  setup(fakeApi());
  expect(await screen.findByText("Google Maps · recenze od 01/2026 do 02/2026")).toBeInTheDocument();
});

it("lists every Source of the Company in the sub-line", async () => {
  setup(fakeApi({ runResult: vi.fn(async () => twoSources()) }));
  expect(await screen.findByText("Google Maps, Firmy.cz · recenze od 06/2025 do 06/2026")).toBeInTheDocument();
});

it("draws every distribution bar in black", async () => {
  setup(fakeApi());
  const card = await screen.findByRole("group", { name: "Rozdělení hodnocení" });
  const fills = [...card.querySelectorAll("button span[aria-hidden] > span")];
  expect(fills).toHaveLength(5);
  for (const fill of fills) expect(fill).toHaveClass("bg-ink");
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

it("puts the Topics in a grid under the chart", async () => {
  const withTopics = fakeResult({
    topics: [{ key: "service", name: "Obsluha" }],
    metrics: { ...fakeResult().metrics, topic_shares: [{ topic_key: "service", positive: 3, neutral: 0, negative: 1 }] },
  });
  setup(fakeApi({ runResult: vi.fn(async () => withTopics) }));
  const chart = (await screen.findByRole("heading", { name: "Vývoj hodnocení" })).closest("section")!;
  const list = screen.getByRole("list", { name: "Témata" });
  expect(chart.compareDocumentPosition(list) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
  expect(list).toHaveClass("grid");
  expect(screen.queryByText("Pozitivní")).not.toBeInTheDocument();
});

it("uses the 1280 px wide page of the design", async () => {
  setup(fakeApi());
  expect(await screen.findByRole("main")).toHaveClass("max-w-7xl");
});

it("remembers the opened result for the Search screen", async () => {
  localStorage.clear();
  setup(fakeApi());
  await screen.findByRole("heading", { level: 1, name: "Kavárna U Mlýna" });
  expect(readRecent(Date.now())).toMatchObject([{ run_id: "run-1", name: "Kavárna U Mlýna" }]);
});

/** The matchers normalize the non-breaking space of the thousands separator to a plain one. */
const NBSP = " ";

/** The default Place of the fake result with some of its fields replaced. */
function withPlace(place: Partial<RunResult["places"][number]>) {
  const base = fakeResult();
  return fakeResult({ places: [{ ...base.places[0]!, ...place }] });
}

const fullPlace = {
  category: "Kavárna",
  address: "Mlýnská 1, Praha",
  phone: "+420 123 456 789",
  website: "https://umlyna.example",
  maps_url: "https://maps.example/umlyna",
  thumbnail_url: "https://img.example/umlyna.jpg",
};

it("shows who the Place is: category, address, phone, website, Maps link and thumbnail", async () => {
  setup(fakeApi({ runResult: vi.fn(async () => withPlace(fullPlace)) }));
  const header = await screen.findByRole("group", { name: "Údaje o místě" });
  expect(within(header).getByText("Kavárna")).toBeInTheDocument();
  expect(within(header).getByText("Mlýnská 1, Praha")).toBeInTheDocument();
  expect(within(header).getByText("+420 123 456 789")).toBeInTheDocument();
  const website = within(header).getByRole("link", { name: "umlyna.example" });
  expect(website).toHaveAttribute("href", "https://umlyna.example");
  const maps = within(header).getByRole("link", { name: "Otevřít v Google Maps" });
  expect(maps).toHaveAttribute("href", "https://maps.example/umlyna");
  for (const link of [website, maps]) {
    expect(link).toHaveAttribute("rel", "noopener noreferrer");
    expect(link).toHaveAttribute("target", "_blank");
  }
  expect(within(header).getByRole("img", { name: "Kavárna U Mlýna" })).toHaveAttribute("src", "https://img.example/umlyna.jpg");
});

it.each(Object.keys(fullPlace))("leaves out only the missing field %s of the Place header", async (field) => {
  setup(fakeApi({ runResult: vi.fn(async () => withPlace({ ...fullPlace, [field]: null })) }));
  await screen.findByRole("heading", { level: 1 });
  const present = {
    category: () => screen.queryByText("Kavárna"),
    address: () => screen.queryByText("Mlýnská 1, Praha"),
    phone: () => screen.queryByText("+420 123 456 789"),
    website: () => screen.queryByRole("link", { name: "umlyna.example" }),
    maps_url: () => screen.queryByRole("link", { name: "Otevřít v Google Maps" }),
    thumbnail_url: () => screen.queryByRole("img", { name: "Kavárna U Mlýna" }),
  };
  for (const [key, find] of Object.entries(present)) {
    if (key === field) expect(find()).not.toBeInTheDocument();
    else expect(find()).toBeInTheDocument();
  }
});

it("shows no Place header at all when the Place has no details", async () => {
  setup(fakeApi({ runResult: vi.fn(async () => withPlace({ category: null, address: null })) }));
  await screen.findByRole("heading", { level: 1 });
  expect(screen.queryByRole("group", { name: "Údaje o místě" })).not.toBeInTheDocument();
  expect(screen.queryByRole("link", { name: "Otevřít v Google Maps" })).not.toBeInTheDocument();
  expect(screen.queryByRole("img", { name: "Kavárna U Mlýna" })).not.toBeInTheDocument();
});

it("takes the rating and the Review count of the box from Google Maps, not from the analyzed Reviews", async () => {
  const result = withPlace({ rating: 4.6, review_count: 26348, reviews_per_rating: { 5: 20000, 4: 4000, 3: 1500, 2: 500, 1: 348 }, analyzed_count: 1000, analyzed_is_limited: true });
  setup(fakeApi({ runResult: vi.fn(async () => result) }));
  const google = await screen.findByRole("group", { name: "Google Maps" });
  expect(within(google).getByText("4,6")).toBeInTheDocument();
  expect(within(google).getByText(`26${NBSP}348 recenzí`)).toBeInTheDocument();
});

it("says the analysis covers only the newest Reviews when the Place has more", async () => {
  const result = withPlace({ rating: 4.6, review_count: 26348, reviews_per_rating: { 5: 26348 }, analyzed_count: 1000, analyzed_is_limited: true });
  setup(fakeApi({ runResult: vi.fn(async () => result) }));
  const note = await screen.findByRole("status");
  expect(note).toHaveTextContent(`Na Google Maps je 26${NBSP}348 hodnocení, analyzujeme posledních 1${NBSP}000.`);
});

it("shows no limit note when every Review is analyzed", async () => {
  setup(fakeApi());
  await screen.findByRole("heading", { level: 1 });
  expect(screen.queryByText(/analyzujeme posledních/)).not.toBeInTheDocument();
});

it("falls back to the analyzed numbers and shows no limit note when the Google Maps totals are missing", async () => {
  const result = withPlace({ rating: null, review_count: null, reviews_per_rating: null, analyzed_is_limited: true });
  setup(fakeApi({ runResult: vi.fn(async () => result) }));
  const google = await screen.findByRole("group", { name: "Google Maps" });
  expect(within(google).getByText("4,0")).toBeInTheDocument();
  expect(within(google).getByText("18 recenzí")).toBeInTheDocument();
  expect(screen.queryByText(/analyzujeme posledních/)).not.toBeInTheDocument();
  const rows = within(screen.getByRole("group", { name: "Rozdělení hodnocení" })).getAllByRole("button");
  expect(rows[0]).toHaveAccessibleName("5 ★, 8 recenzí, 44 %");
});

it("builds the star distribution from the Google Maps counts and puts it under the boxes", async () => {
  const result = withPlace({ rating: 4.6, review_count: 1100, reviews_per_rating: { 5: 800, 4: 200, 3: 50, 2: 30, 1: 20 }, analyzed_count: 1000, analyzed_is_limited: true });
  setup(fakeApi({ runResult: vi.fn(async () => result) }));
  const distribution = await screen.findByRole("group", { name: "Rozdělení hodnocení" });
  const rows = within(distribution).getAllByRole("button");
  const counts = rows.map((row) => Number(/, (\d+) recenz/.exec(row.getAttribute("aria-label")!)![1]));
  expect(counts).toEqual([800, 200, 50, 30, 20]);
  expect(counts.reduce((a, b) => a + b, 0)).toBe(1100);
  expect(within(distribution).getByText(`Všech 1${NBSP}100 recenzí`)).toBeInTheDocument();
  const boxes = screen.getByRole("group", { name: "Náklady analýzy" });
  const timeline = screen.getByRole("heading", { name: "Vývoj hodnocení" });
  expect(boxes.compareDocumentPosition(distribution) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
  expect(distribution.compareDocumentPosition(timeline) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
});

it("keeps Reviews without text in the counts and does not say they were dropped", async () => {
  setup(fakeApi());
  await screen.findByRole("heading", { level: 1 });
  expect(screen.queryByText(/vyřazeno|vyřazen/i)).not.toBeInTheDocument();
});

it("writes the count of every distribution row with the thousands separator", async () => {
  const result = withPlace({ rating: 4.6, review_count: 26348, reviews_per_rating: { 5: 20000, 4: 4000, 3: 1500, 2: 500, 1: 348 }, analyzed_count: 1000, analyzed_is_limited: true });
  setup(fakeApi({ runResult: vi.fn(async () => result) }));
  const rows = within(await screen.findByRole("group", { name: "Rozdělení hodnocení" })).getAllByRole("button");
  expect(rows.map((row) => row.textContent)).toEqual([`5 ★20\u00a0000 · 76 %`, `4 ★4\u00a0000 · 15 %`, `3 ★1\u00a0500 · 6 %`, "2 ★500 · 2 %", "1 ★348 · 1 %"]);
});
