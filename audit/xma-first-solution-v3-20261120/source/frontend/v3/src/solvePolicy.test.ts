import { describe, expect, it } from "vitest";
import { recommendSeconds } from "./solvePolicy";
import type { DraftDocument } from "./types";

describe("runtime recommendation", () => {
  it("increases with flights, candidates and fleet assignment scale", () => {
    const doc = (flights: number, aircraft: number, candidates: number) => ({ solve_bundle: {
      scenario: { flights: Array(flights), aircraft: Array(aircraft) },
      recovery_columns: { flight_options: Array(candidates) },
    } }) as unknown as DraftDocument;
    expect(recommendSeconds(doc(7, 3, 42))).toBe(600);
    expect(recommendSeconds(doc(50, 17, 300))).toBe(1800);
    expect(recommendSeconds(doc(100, 34, 600))).toBe(3600);
    expect(recommendSeconds(doc(500, 80, 3000))).toBe(7200);
    expect(recommendSeconds(doc(1000, 80, 6000))).toBe(14400);
  });
});
