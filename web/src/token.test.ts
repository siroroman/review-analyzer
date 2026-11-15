import { readDemoToken } from "./token";

afterEach(() => {
  sessionStorage.clear();
  window.history.replaceState(null, "", "/");
  vi.restoreAllMocks();
});

it("keeps the other parts of the address when it removes the token", () => {
  window.history.replaceState(null, "", "/runs/r1?token=abc&x=1#top");
  expect(readDemoToken()).toBe("abc");
  expect(window.location.pathname + window.location.search + window.location.hash).toBe("/runs/r1?x=1#top");
});

it("works for the page's lifetime when the storage is blocked", () => {
  vi.spyOn(Storage.prototype, "setItem").mockImplementation(() => {
    throw new Error("blocked");
  });
  vi.spyOn(Storage.prototype, "getItem").mockImplementation(() => {
    throw new Error("blocked");
  });
  window.history.replaceState(null, "", "/?token=abc");
  expect(readDemoToken()).toBe("abc");
  expect(readDemoToken()).toBeNull();
});
