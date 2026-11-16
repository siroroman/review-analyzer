import { formatCost, formatUsd } from "./steps";

it("shows costs in Czech notation: two decimals, three for amounts under a cent", () => {
  expect(formatUsd("0")).toBe("0,00 USD");
  expect(formatUsd("0.1234")).toBe("0,12 USD");
  expect(formatUsd("0.003")).toBe("0,003 USD");
  expect(formatUsd("1.5")).toBe("1,50 USD");
});

it("keeps the Result screen's cost format", () => {
  expect(formatCost("0.1234")).toBe("0.123 USD");
  expect(formatCost("1.5")).toBe("1.50 USD");
});
