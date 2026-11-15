import { render } from "@testing-library/react";
import { useApi } from "./context";

it("refuses to run without a provider", () => {
  vi.spyOn(console, "error").mockImplementation(() => {});
  function Probe() {
    useApi();
    return null;
  }
  expect(() => render(<Probe />)).toThrow(/ApiProvider/);
});
