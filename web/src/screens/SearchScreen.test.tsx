import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { ApiError } from "../api/client";
import { ApiProvider } from "../api/context";
import { fakeApi } from "../fakeApi";
import { rememberRun } from "../recentRuns";
import { SearchScreen } from "./SearchScreen";

const CAFE = { place_id: "g1", text: "Kavárna Slavia, Praha" };

function setup(api = fakeApi()) {
  vi.useFakeTimers({ shouldAdvanceTime: true });
  const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
  render(
    <ApiProvider api={api}>
      <MemoryRouter>
        <Routes>
          <Route path="/" element={<SearchScreen />} />
          <Route path="/runs/:id" element={<p>progress of the Run</p>} />
        </Routes>
      </MemoryRouter>
    </ApiProvider>,
  );
  return { api, user };
}

beforeEach(() => localStorage.clear());
afterEach(() => vi.useRealTimers());

async function search(user: ReturnType<typeof userEvent.setup>, text = "kav") {
  await user.type(screen.getByRole("searchbox"), text);
  vi.advanceTimersByTime(400);
}

describe("layout from the design", () => {
  it("shows the app header and the headline with an input named only by aria-label", () => {
    setup();
    expect(screen.getByRole("banner")).toHaveTextContent("Review Analyzer");
    expect(screen.getByRole("heading", { level: 1 })).toBeInTheDocument();
    const input = screen.getByRole("searchbox", { name: "Název firmy" });
    expect(input).toHaveAttribute("aria-label", "Název firmy");
    expect(input).toHaveAttribute("placeholder", "Např. Alza cz");
  });

  it("has no visible label, no hint paragraph and no sources line", () => {
    setup();
    expect(screen.queryByText("Firma nebo pobočka")).not.toBeInTheDocument();
    expect(screen.queryByText(/Návrhy pocházejí/)).not.toBeInTheDocument();
    expect(screen.queryByText(/Zdroje:/)).not.toBeInTheDocument();
  });

  it("lists each found Place once, with no group headings", async () => {
    const other = { place_id: "g2", text: "Kavárna Louvre, Praha" };
    const { user } = setup(fakeApi({ suggest: vi.fn(async () => [CAFE, other]) }));
    await search(user);
    const list = await screen.findByRole("list");
    expect(within(list).getAllByRole("button")).toHaveLength(2);
    expect(within(list).getAllByText(CAFE.text)).toHaveLength(1);
    expect(screen.queryByRole("group")).not.toBeInTheDocument();
    expect(screen.queryByText(/celá firma|jedna pobočka|jen tato pobočka/i)).not.toBeInTheDocument();
  });
});

describe("autocomplete", () => {
  it("asks once, after the typing stops", async () => {
    const api = fakeApi({ suggest: vi.fn(async () => [CAFE]) });
    const { user } = setup(api);
    await search(user);
    expect((await screen.findAllByText(CAFE.text)).length).toBeGreaterThan(0);
    expect(api.suggest).toHaveBeenCalledTimes(1);
    expect(api.suggest.mock.calls[0]?.[0]).toBe("kav");
  });

  it("does not ask for an empty text", async () => {
    const { api, user } = setup();
    await search(user, "  ");
    expect(api.suggest).not.toHaveBeenCalled();
  });

  it("says when nothing was found", async () => {
    const { user } = setup();
    await search(user);
    expect(await screen.findByText(/nic jsme nenašli/i)).toBeInTheDocument();
  });

  it("says when the search is unavailable", async () => {
    const { user } = setup(fakeApi({ suggest: vi.fn(async () => Promise.reject(new ApiError(503))) }));
    await search(user);
    expect(await screen.findByRole("alert")).toHaveTextContent(/zkuste to znovu/i);
  });

  it("explains a missing or wrong Demo token", async () => {
    const { user } = setup(fakeApi({ suggest: vi.fn(async () => Promise.reject(new ApiError(401))) }));
    await search(user);
    expect(await screen.findByRole("alert")).toHaveTextContent(/odkaz/i);
  });

  it("drops a stale answer when the text changed", async () => {
    let first: (value: (typeof CAFE)[]) => void = () => {};
    const suggest = vi
      .fn()
      .mockImplementationOnce(() => new Promise((resolve) => (first = resolve)))
      .mockResolvedValueOnce([{ place_id: "g2", text: "Nová" }]);
    const { user } = setup(fakeApi({ suggest }));
    await search(user, "kav");
    await user.type(screen.getByRole("searchbox"), "a");
    vi.advanceTimersByTime(400);
    expect((await screen.findAllByText("Nová")).length).toBeGreaterThan(0);
    first([CAFE]);
    await Promise.resolve();
    expect(screen.queryByText(CAFE.text)).not.toBeInTheDocument();
  });
});

describe("choosing one Place", () => {
  const analyze = () => screen.getByRole("button", { name: "Analyzovat recenze" });
  const pick = async (user: ReturnType<typeof userEvent.setup>) => user.click(await screen.findByRole("button", { name: new RegExp(CAFE.text) }));

  it("keeps the button disabled until a suggestion is chosen", async () => {
    const { user } = setup(fakeApi({ suggest: vi.fn(async () => [CAFE]) }));
    expect(analyze()).toBeDisabled();
    await search(user);
    await screen.findByRole("list");
    expect(analyze()).toBeDisabled();
  });

  it("fills the input with the choice, closes the list and enables the button", async () => {
    const { user } = setup(fakeApi({ suggest: vi.fn(async () => [CAFE]) }));
    await search(user);
    await pick(user);
    expect(screen.getByRole("searchbox")).toHaveValue(CAFE.text);
    expect(screen.queryByRole("list")).not.toBeInTheDocument();
    expect(analyze()).toBeEnabled();
  });

  it("does not ask for suggestions again for the text it filled in", async () => {
    const api = fakeApi({ suggest: vi.fn(async () => [CAFE]) });
    const { user } = setup(api);
    await search(user);
    await pick(user);
    vi.advanceTimersByTime(400);
    await Promise.resolve();
    expect(api.suggest).toHaveBeenCalledTimes(1);
    expect(screen.queryByRole("list")).not.toBeInTheDocument();
  });

  it("disables the button again when the text is edited", async () => {
    const { user } = setup(fakeApi({ suggest: vi.fn(async () => [CAFE]) }));
    await search(user);
    await pick(user);
    await user.type(screen.getByRole("searchbox"), "x");
    expect(analyze()).toBeDisabled();
  });

  it("starts a Run for that Place only and opens its progress", async () => {
    const api = fakeApi({ suggest: vi.fn(async () => [CAFE]) });
    const { user } = setup(api);
    await search(user);
    await pick(user);
    await user.click(analyze());
    expect(api.startRun).toHaveBeenCalledWith({ place_ids: ["g1"] });
    expect(await screen.findByText("progress of the Run")).toBeInTheDocument();
    expect(api.branches).not.toHaveBeenCalled();
  });

  it("asks for no branches, name or industry", async () => {
    const { user } = setup(fakeApi({ suggest: vi.fn(async () => [CAFE]) }));
    await search(user);
    await pick(user);
    expect(screen.queryByRole("checkbox")).not.toBeInTheDocument();
    expect(screen.queryByLabelText(/^název$/i)).not.toBeInTheDocument();
    expect(screen.queryByLabelText(/obor/i)).not.toBeInTheDocument();
  });

  it("shows why a Run could not start and allows another try", async () => {
    const api = fakeApi({
      suggest: vi.fn(async () => [CAFE]),
      startRun: vi.fn(async () => Promise.reject(new ApiError(429))),
    });
    const { user } = setup(api);
    await search(user);
    await pick(user);
    await user.click(analyze());
    expect(await screen.findByRole("alert")).toHaveTextContent(/limit/i);
    expect(analyze()).toBeEnabled();
  });
});

describe("recently analyzed", () => {
  it("is hidden when no result was opened", () => {
    setup();
    expect(screen.queryByText(/nedávno analyzované/i)).not.toBeInTheDocument();
  });

  it("links to the results opened in this browser, in the last 24 hours", () => {
    rememberRun("run-7", "Alza.cz a.s.", Date.now());
    rememberRun("run-old", "Stará firma", Date.now() - 25 * 3_600_000);
    setup();
    expect(screen.getByText("Nedávno analyzované (v cache 24 h)")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Alza.cz a.s." })).toHaveAttribute("href", "/runs/run-7/result");
    expect(screen.queryByRole("link", { name: "Stará firma" })).not.toBeInTheDocument();
  });
});
