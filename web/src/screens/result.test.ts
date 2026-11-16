import { ratingAxis } from "./result";

const trend = (...ratings: number[]) => ratings.map((average_rating, index) => ({ source: "google_maps" as const, period_start: `2026-0${index + 1}-01`, average_rating, count: 10, sentiment: 0 }));

describe("ratingAxis", () => {
  it("pads the data by a quarter star and rounds out to half stars", () => {
    expect(ratingAxis(trend(3.7, 4.6))).toEqual({ domain: [3, 5], ticks: [3, 3.5, 4, 4.5, 5] });
  });

  it("never goes beyond 1 to 5", () => {
    expect(ratingAxis(trend(1, 5)).domain).toEqual([1, 5]);
  });

  it("keeps at least a star of height for a flat line at the top", () => {
    expect(ratingAxis(trend(5, 5)).domain).toEqual([4, 5]);
  });

  it("shows the whole scale when there is no data", () => {
    expect(ratingAxis([]).domain).toEqual([1, 5]);
  });
});
