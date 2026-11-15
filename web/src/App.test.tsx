import { render, screen } from "@testing-library/react";
import { App } from "./App";

afterEach(() => {
  sessionStorage.clear();
  window.history.replaceState(null, "", "/");
});

it("says the link is missing when there is no Demo token", () => {
  render(<App />);
  expect(screen.getByRole("alert")).toHaveTextContent(/odkaz/i);
});

it("takes the Demo token from the link, removes it from the address and shows the search", () => {
  window.history.replaceState(null, "", "/?token=abc");
  render(<App />);
  expect(screen.getByRole("searchbox")).toBeInTheDocument();
  expect(window.location.search).toBe("");
  expect(sessionStorage.getItem("demo-token")).toBe("abc");
});

it("keeps the token for the session, so a reopened Run link works", () => {
  sessionStorage.setItem("demo-token", "abc");
  window.history.replaceState(null, "", "/runs/run-1");
  render(<App />);
  expect(screen.getByRole("heading", { name: /průběh analýzy/i })).toBeInTheDocument();
});
