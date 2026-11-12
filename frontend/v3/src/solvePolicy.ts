import type { DraftDocument } from "./types";

const object = (value: unknown): Record<string, unknown> => value && typeof value === "object" ? value as Record<string, unknown> : {};
const length = (value: unknown) => Array.isArray(value) ? value.length : 0;

export function recommendSeconds(doc: DraftDocument | null) {
  const bundle = object(doc?.solve_bundle);
  const scenario = object(bundle.dataset ?? bundle.scenario ?? doc?.scenario);
  const flights = length(scenario.flights), tails = length(scenario.aircraft);
  const columns = object(bundle.recovery_columns);
  const candidates = length(columns.flight_options) || flights * (Math.ceil(Number(bundle.maximum_delay_minutes ?? 120) / Number(bundle.delay_step_minutes ?? 30)) + 2);
  const tier = (count: number, bounds: number[]) => { const index = bounds.findIndex(bound => count <= bound); return index < 0 ? 4 : index; };
  return [600, 1800, 3600, 7200, 14400][Math.max(tier(flights, [12, 50, 100, 500]), tier(candidates, [100, 1000, 5000, 20000]), tier(candidates * tails, [1000, 10000, 100000, 1000000]))];
}
