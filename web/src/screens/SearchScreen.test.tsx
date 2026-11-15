import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { ApiError } from "../api/client";
import { ApiProvider } from "../api/context";
import { fakeApi } from "../fakeApi";
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

afterEach(() => vi.useRealTimers());

async function search(user: ReturnType<typeof userEvent.setup>, text = "kav") {
  await user.type(screen.getByRole("searchbox"), text);
  vi.advanceTimersByTime(400);
}

describe("autocomplete", () => {
  it("asks once, after the typing stops", async () => {
    const api = fakeApi({ suggest: vi.fn(async () => [CAFE]) });
    const { user } = setup(api);
    await search(user);
    expect(await screen.findByText(CAFE.text)).toBeInTheDocument();
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
    expect(await screen.findByText("Nová")).toBeInTheDocument();
    first([CAFE]);
    await Promise.resolve();
    expect(screen.queryByText(CAFE.text)).not.toBeInTheDocument();
  });
});

describe("choosing exactly one Place", () => {
  it("starts a Run for that Place only", async () => {
    const api = fakeApi({ suggest: vi.fn(async () => [CAFE]) });
    const { user } = setup(api);
    await search(user);
    await user.click(await screen.findByRole("button", { name: /jen tato pobočka/i }));
    expect(screen.getByLabelText(/název/i)).toHaveValue("Kavárna Slavia");
    await user.type(screen.getByLabelText(/obor/i), "kavárna");
    await user.click(screen.getByRole("button", { name: /spustit analýzu/i }));
    expect(api.startRun).toHaveBeenCalledWith({ place_ids: ["g1"], name: "Kavárna Slavia", industry: "kavárna" });
    expect(await screen.findByText("progress of the Run")).toBeInTheDocument();
    expect(api.branches).not.toHaveBeenCalled();
  });

  it("needs an industry", async () => {
    const api = fakeApi({ suggest: vi.fn(async () => [CAFE]) });
    const { user } = setup(api);
    await search(user);
    await user.click(await screen.findByRole("button", { name: /jen tato pobočka/i }));
    await user.click(screen.getByRole("button", { name: /spustit analýzu/i }));
    expect(api.startRun).not.toHaveBeenCalled();
    expect(screen.getByRole("alert")).toHaveTextContent(/obor/i);
  });

  it("goes back to the search", async () => {
    const { user } = setup(fakeApi({ suggest: vi.fn(async () => [CAFE]) }));
    await search(user);
    await user.click(await screen.findByRole("button", { name: /jen tato pobočka/i }));
    await user.click(screen.getByRole("button", { name: /zpět/i }));
    expect(screen.getByRole("searchbox")).toBeInTheDocument();
  });

  it("shows why a Run could not start", async () => {
    const api = fakeApi({
      suggest: vi.fn(async () => [CAFE]),
      startRun: vi.fn(async () => Promise.reject(new ApiError(429))),
    });
    const { user } = setup(api);
    await search(user);
    await user.click(await screen.findByRole("button", { name: /jen tato pobočka/i }));
    await user.type(screen.getByLabelText(/obor/i), "kavárna");
    await user.click(screen.getByRole("button", { name: /spustit analýzu/i }));
    expect(await screen.findByRole("alert")).toHaveTextContent(/limit/i);
  });
});

describe("choosing one Company", () => {
  const branches = [
    { place_id: "g2", name: "Kavárna Slavia", address: "Brno" },
    { place_id: "g3", name: "Hypermarket Kavárna", address: "Plzeň" },
  ];

  it("lets the user remove false branches before the Run starts", async () => {
    const api = fakeApi({ suggest: vi.fn(async () => [CAFE]), branches: vi.fn(async () => branches) });
    const { user } = setup(api);
    await search(user);
    await user.click(await screen.findByRole("button", { name: /celá firma/i }));
    expect(api.branches).toHaveBeenCalledWith("g1");
    await user.click(await screen.findByRole("checkbox", { name: /hypermarket kavárna/i }));
    await user.type(screen.getByLabelText(/obor/i), "kavárna");
    await user.click(screen.getByRole("button", { name: /spustit analýzu/i }));
    await waitFor(() => expect(api.startRun).toHaveBeenCalled());
    expect(api.startRun).toHaveBeenCalledWith({
      place_ids: ["g1", "g2"],
      name: "Kavárna Slavia",
      industry: "kavárna",
    });
  });

  it("keeps the chosen Place, which cannot be removed", async () => {
    const { user } = setup(fakeApi({ suggest: vi.fn(async () => [CAFE]), branches: vi.fn(async () => branches) }));
    await search(user);
    await user.click(await screen.findByRole("button", { name: /celá firma/i }));
    expect(await screen.findByRole("checkbox", { name: /kavárna slavia, praha/i })).toBeDisabled();
  });

  it("works for a Company without other branches", async () => {
    const { user } = setup(fakeApi({ suggest: vi.fn(async () => [CAFE]) }));
    await search(user);
    await user.click(await screen.findByRole("button", { name: /celá firma/i }));
    expect(await screen.findByText(/žádné další pobočky/i)).toBeInTheDocument();
  });

  it("says when the branches could not be found", async () => {
    const { user } = setup(
      fakeApi({ suggest: vi.fn(async () => [CAFE]), branches: vi.fn(async () => Promise.reject(new ApiError(503))) }),
    );
    await search(user);
    await user.click(await screen.findByRole("button", { name: /celá firma/i }));
    expect(await screen.findByRole("alert")).toHaveTextContent(/pobočky/i);
  });
});
