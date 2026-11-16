import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { ApiError, type ReviewView } from "../api/client";
import { ApiProvider } from "../api/context";
import { fakeApi, fakeResult } from "../fakeApi";
import { ResultScreen } from "./ResultScreen";

function setup(api: ReturnType<typeof fakeApi>) {
  return render(
    <ApiProvider api={api}>
      <MemoryRouter initialEntries={["/runs/run-1/result"]}>
        <Routes>
          <Route path="/runs/:id/result" element={<ResultScreen />} />
        </Routes>
      </MemoryRouter>
    </ApiProvider>,
  );
}

const review = (id: string, text: string, rating = 2): ReviewView => ({
  id,
  source: "google_maps",
  place_name: "Kavárna Vinohrady",
  rating,
  date: "2026-02-14",
  text,
});

const withTopics = () =>
  fakeResult({
    topics: [
      { key: "service", name: "Obsluha" },
      { key: "price", name: "Cena" },
    ],
    metrics: {
      ...fakeResult().metrics,
      topic_shares: [
        { topic_key: "service", positive: 2, neutral: 0, negative: 6 },
        { topic_key: "price", positive: 3, neutral: 1, negative: 0 },
      ],
    },
  });

describe("Topics", () => {
  it("lists a Topic per row with its mentions and the positive and negative share", async () => {
    setup(fakeApi({ runResult: vi.fn(async () => withTopics()) }));
    const list = await screen.findByRole("list", { name: "Témata" });
    const [service, price] = within(list).getAllByRole("listitem");
    expect(service).toHaveTextContent("Obsluha");
    expect(service).toHaveTextContent("8 zmínek");
    expect(service).toHaveTextContent("25 % pozitivních, 75 % negativních");
    expect(price).toHaveTextContent("4 zmínky");
    expect(screen.getByText("Pozitivní")).toBeInTheDocument();
    expect(screen.getByText("Negativní")).toBeInTheDocument();
  });

  it("opens the cited Reviews of a Topic in a side panel", async () => {
    const user = userEvent.setup();
    const reviews = vi.fn(async () => [review("r1", "Čekali jsme půl hodiny.")]);
    const api = fakeApi({ runResult: vi.fn(async () => withTopics()), reviews });
    setup(api);
    await user.click(await screen.findByRole("button", { name: /Obsluha/ }));
    const panel = await screen.findByRole("dialog", { name: "Recenze: Obsluha" });
    expect(await within(panel).findByText("Čekali jsme půl hodiny.")).toBeInTheDocument();
    expect(within(panel).getByText(/Kavárna Vinohrady/)).toBeInTheDocument();
    expect(reviews).toHaveBeenCalledWith("run-1", { topic: "service" });
    expect(screen.getByRole("button", { name: /Obsluha/ })).toHaveAttribute("aria-pressed", "true");
  });

  it("closes the panel with the button and with Escape", async () => {
    const user = userEvent.setup();
    setup(fakeApi({ runResult: vi.fn(async () => withTopics()), reviews: vi.fn(async () => [review("r1", "Text")]) }));
    await user.click(await screen.findByRole("button", { name: /Obsluha/ }));
    await screen.findByRole("dialog");
    await user.click(screen.getByRole("button", { name: "Zavřít" }));
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: /Obsluha/ }));
    await screen.findByRole("dialog");
    await user.keyboard("{Escape}");
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Obsluha/ })).toHaveFocus();
  });

  it("says so when the Reviews cannot be loaded or there are none", async () => {
    const user = userEvent.setup();
    const reviews = vi.fn<() => Promise<ReviewView[]>>().mockRejectedValueOnce(new ApiError(501)).mockResolvedValueOnce([]);
    setup(fakeApi({ runResult: vi.fn(async () => withTopics()), reviews }));
    await user.click(await screen.findByRole("button", { name: /Obsluha/ }));
    expect(await within(await screen.findByRole("dialog")).findByRole("alert")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Zavřít" }));
    await user.click(screen.getByRole("button", { name: /Cena/ }));
    expect(await within(await screen.findByRole("dialog")).findByText("Žádné recenze k zobrazení.")).toBeInTheDocument();
  });

  it("shows no Topics card when the Run found no Topic", async () => {
    setup(fakeApi());
    await screen.findByRole("heading", { level: 1 });
    expect(screen.queryByRole("list", { name: "Témata" })).not.toBeInTheDocument();
  });
});

describe("Summary and suggestions", () => {
  const insights = () =>
    fakeResult({
      insights: [
        { type: "summary", period_start: "2026-01-01", period_end: "2026-02-28", text: "Hodnocení kleslo kvůli čekání.", review_ids: ["r1", "r2"] },
        { type: "suggestion", period_start: "2026-01-01", period_end: "2026-02-28", text: "Přidat druhou pokladnu.", review_ids: ["r3"] },
        { type: "suggestion", period_start: "2026-01-01", period_end: "2026-02-28", text: "Zaškolit obsluhu.", review_ids: ["r4"] },
        { type: "anomaly", period_start: "2026-02-01", period_end: "2026-02-28", text: "Únor byl slabý.", review_ids: ["r5"] },
      ],
    });

  it("shows the summary, numbered suggestions and the note that every statement links to Reviews", async () => {
    setup(fakeApi({ runResult: vi.fn(async () => insights()) }));
    expect(await screen.findByText("Hodnocení kleslo kvůli čekání.")).toBeInTheDocument();
    const list = screen.getByRole("list", { name: "Doporučení" });
    const items = within(list).getAllByRole("listitem");
    expect(items).toHaveLength(2);
    expect(items[0]).toHaveTextContent("1");
    expect(items[0]).toHaveTextContent("Přidat druhou pokladnu.");
    expect(items[1]).toHaveTextContent("Zaškolit obsluhu.");
    expect(screen.getByText(/Každé tvrzení odkazuje na recenze/)).toBeInTheDocument();
  });

  it("opens the Reviews an insight cites by their IDs", async () => {
    const user = userEvent.setup();
    const reviews = vi.fn(async () => [review("r3", "Fronta u pokladny.")]);
    setup(fakeApi({ runResult: vi.fn(async () => insights()), reviews }));
    const list = await screen.findByRole("list", { name: "Doporučení" });
    await user.click(within(list).getAllByRole("button", { name: /Zobrazit recenze/ })[0]!);
    const panel = await screen.findByRole("dialog");
    expect(await within(panel).findByText("Fronta u pokladny.")).toBeInTheDocument();
    expect(reviews).toHaveBeenCalledWith("run-1", { ids: ["r3"] });
  });

  it("opens the Reviews of the summary", async () => {
    const user = userEvent.setup();
    const reviews = vi.fn(async () => [review("r1", "Moc dlouho.")]);
    setup(fakeApi({ runResult: vi.fn(async () => insights()), reviews }));
    await user.click(await screen.findByRole("button", { name: "Zobrazit recenze (2)" }));
    expect(reviews).toHaveBeenCalledWith("run-1", { ids: ["r1", "r2"] });
  });

  it("shows nothing when there are no insights", async () => {
    setup(fakeApi());
    await screen.findByRole("heading", { level: 1 });
    expect(screen.queryByRole("list", { name: "Doporučení" })).not.toBeInTheDocument();
  });
});

describe("Branch comparison", () => {
  const branches = () =>
    fakeResult({
      topics: [{ key: "service", name: "Obsluha" }],
      company: {
        name: "Kavárna U Mlýna",
        industry: "cafe",
        places: [
          { source: "google_maps", external_id: "g1", name: "Kavárna Vinohrady", address: "Praha 2" },
          { source: "google_maps", external_id: "g2", name: "Kavárna Smíchov", address: "Praha 5" },
        ],
      },
      metrics: {
        ...fakeResult().metrics,
        per_place: [
          { source: "google_maps", place_external_id: "g1", summary: { average_rating: 4.4, count: 30 }, main_topic_key: null },
          { source: "google_maps", place_external_id: "g2", summary: { average_rating: 3.1, count: 12 }, main_topic_key: "service" },
        ],
      },
    });

  it("lists the branches and marks the weakest one with a triangle, not by colour alone", async () => {
    setup(fakeApi({ runResult: vi.fn(async () => branches()) }));
    const table = await screen.findByRole("table", { name: "Srovnání poboček" });
    const rows = within(table).getAllByRole("row");
    expect(rows[0]).toHaveTextContent("PobočkaHodnoceníRecenzeHlavní problém");
    expect(rows[1]).toHaveTextContent("Kavárna Vinohrady");
    expect(rows[1]).toHaveTextContent("4,4");
    expect(rows[1]).toHaveTextContent("30");
    expect(rows[1]).not.toHaveTextContent("▼");
    expect(rows[2]).toHaveTextContent("▼");
    expect(rows[2]).toHaveTextContent("Kavárna Smíchov");
    expect(rows[2]).toHaveTextContent("Obsluha");
  });

  it("marks no branch as weakest when there is only one", async () => {
    setup(fakeApi());
    await screen.findByRole("heading", { level: 1 });
    expect(screen.queryByRole("table", { name: "Srovnání poboček" })).not.toBeInTheDocument();
  });
});

describe("Cost of the Run", () => {
  it("shows the cost per Service and the number of excluded suspicious Reviews", async () => {
    const result = fakeResult({ cost: "1.50", flagged: 3, cost_by_service: { apify: "0.90", models: "0.55", google_places: "0.05" } });
    setup(fakeApi({ runResult: vi.fn(async () => result) }));
    const card = await screen.findByRole("group", { name: "Náklady podle služeb" });
    expect(within(card).getByText("Apify").nextSibling).toHaveTextContent("0.900 USD");
    expect(within(card).getByText("Modely").nextSibling).toHaveTextContent("0.550 USD");
    expect(within(card).getByText("Google Places").nextSibling).toHaveTextContent("0.050 USD");
    expect(within(card).getByText("3 podezřelé recenze vyřazeny")).toBeInTheDocument();
  });

  it("says no Review was excluded and shows no breakdown when the API gives none", async () => {
    setup(fakeApi());
    const card = await screen.findByRole("group", { name: "Náklady podle služeb" });
    expect(within(card).getByText("Rozpis zatím není k dispozici.")).toBeInTheDocument();
    expect(within(card).getByText("0 podezřelých recenzí vyřazeno")).toBeInTheDocument();
  });

  it("uses the singular and the five-plus plural", async () => {
    const { unmount } = setup(fakeApi({ runResult: vi.fn(async () => fakeResult({ flagged: 1 })) }));
    expect(await screen.findByText("1 podezřelá recenze vyřazena")).toBeInTheDocument();
    unmount();
    setup(fakeApi({ runResult: vi.fn(async () => fakeResult({ flagged: 7 })) }));
    expect(await screen.findByText("7 podezřelých recenzí vyřazeno")).toBeInTheDocument();
  });
});
