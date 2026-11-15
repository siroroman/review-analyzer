import { formatCost } from "./steps";

it("shows small costs with three decimals and larger ones with two", () => {
  expect(formatCost("0")).toBe("0.000 USD");
  expect(formatCost("0.1234")).toBe("0.123 USD");
  expect(formatCost("1.5")).toBe("1.50 USD");
});
