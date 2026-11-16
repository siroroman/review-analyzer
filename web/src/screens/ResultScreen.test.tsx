import { render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { ApiError } from "../api/client";
import { ApiProvider } from "../api/context";
import { fakeApi } from "../fakeApi";
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
