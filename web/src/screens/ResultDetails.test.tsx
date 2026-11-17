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
    expect(screen.queryByText("Pozitivní")).not.toBeInTheDocument();
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

  it("shows the summary and numbered suggestions without a note about links", async () => {
    setup(fakeApi({ runResult: vi.fn(async () => insights()) }));
    expect(await screen.findByText("Hodnocení kleslo kvůli čekání.")).toBeInTheDocument();
    const list = screen.getByRole("list", { name: "Doporučení" });
    const items = within(list).getAllByRole("listitem");
    expect(items).toHaveLength(2);
    expect(within(items[0]!).getByText("1", { selector: "span" })).toBeInTheDocument();
    expect(within(items[1]!).getByText("2", { selector: "span" })).toBeInTheDocument();
    expect(items[0]).toHaveTextContent("Přidat druhou pokladnu.");
    expect(items[1]).toHaveTextContent("Zaškolit obsluhu.");
    expect(screen.queryByText(/Každé tvrzení odkazuje na recenze/)).not.toBeInTheDocument();
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

  it("highlights the text between ** markers and shows black buttons below the texts", async () => {
    const result = fakeResult({
      insights: [
        { type: "summary", period_start: "2026-01-01", period_end: "2026-02-28", text: "Hodnocení kleslo kvůli **čekání na jídlo**.", review_ids: ["r1"] },
        { type: "suggestion", period_start: "2026-01-01", period_end: "2026-02-28", text: "Zaškolit obsluhu.", review_ids: ["r4"] },
      ],
    });
    setup(fakeApi({ runResult: vi.fn(async () => result) }));
    expect((await screen.findByText("čekání na jídlo")).tagName).toBe("STRONG");
    for (const button of screen.getAllByRole("button", { name: /Zobrazit recenze/ })) expect(button).toHaveClass("bg-ink", "text-white");
    expect(within(screen.getByRole("list", { name: "Doporučení" })).getAllByRole("listitem")[0]).toHaveClass("bg-page");
    for (const button of screen.getAllByRole("button", { name: /Zobrazit recenze/ })) expect(button.parentElement).toHaveClass("flex", "justify-end");
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

  it("shows one branch listed on both Sources as one row and so compares nothing", async () => {
    const both = fakeResult({
      company: {
        name: "Kavárna U Mlýna",
        industry: "cafe",
        places: [
          { source: "google_maps", external_id: "g1", name: "Kavárna Vinohrady", address: "Praha 2" },
          { source: "firmy_cz", external_id: "f1", name: "Kavárna Vinohrady", address: " praha  2 " },
        ],
      },
      metrics: {
        ...fakeResult().metrics,
        per_place: [
          { source: "google_maps", place_external_id: "g1", summary: { average_rating: 4.4, count: 30 } },
          { source: "firmy_cz", place_external_id: "f1", summary: { average_rating: 2.4, count: 10 } },
        ],
      },
    });
    setup(fakeApi({ runResult: vi.fn(async () => both) }));
    await screen.findByRole("heading", { level: 1 });
    expect(screen.queryByRole("table", { name: "Srovnání poboček" })).not.toBeInTheDocument();
  });

  it("merges the Sources of one branch into a weighted rating next to another branch", async () => {
    const result = branches();
    result.company.places.push({ source: "firmy_cz", external_id: "f1", name: "Kavárna Vinohrady", address: "Praha 2" });
    result.company.places[0]!.address = "Praha 2";
    result.metrics.per_place.push({ source: "firmy_cz", place_external_id: "f1", summary: { average_rating: 2.4, count: 10 } });
    setup(fakeApi({ runResult: vi.fn(async () => result) }));
    const table = await screen.findByRole("table", { name: "Srovnání poboček" });
    const rows = within(table).getAllByRole("row");
    expect(rows).toHaveLength(3);
    expect(rows[1]).toHaveTextContent("Google Maps, Firmy.cz");
    expect(rows[1]).toHaveTextContent("3,9");
    expect(rows[1]).toHaveTextContent("40");
  });

  it("marks no branch as weakest when there is only one", async () => {
    setup(fakeApi());
    await screen.findByRole("heading", { level: 1 });
    expect(screen.queryByRole("table", { name: "Srovnání poboček" })).not.toBeInTheDocument();
  });
});
