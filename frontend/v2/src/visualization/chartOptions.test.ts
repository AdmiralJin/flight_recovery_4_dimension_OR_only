import { describe, expect, it } from "vitest";
import type { VisualizationModel } from "../types";
import { flightNetworkOption, ganttOption, propagationOption } from "./chartOptions";

const model: VisualizationModel = {
  schema_version: "1.0.0",
  source_type: "run",
  source_id: "R1",
  draft_id: "D1",
  time_range: { start: "2026-01-01T00:00:00Z", end: "2026-01-01T04:00:00Z", timezone: "UTC" },
  mode_availability: {
    original: { available: true }, impact: { available: true }, recovered: { available: true }, delta: { available: true },
  },
  layer_availability: {}, issues: [],
  disruptions: [{ rule_id: "WX1", rule_type: "airport_closure", airport_id: "AAA", start_time: "2026-01-01T00:30:00Z", end_time: "2026-01-01T01:30:00Z", direction: "both" }],
  flights: [{
    flight_id: "F1",
    original: { origin: "AAA", destination: "BBB", sched_dep: "2026-01-01T01:00:00Z", sched_arr: "2026-01-01T02:00:00Z" },
    effective: {},
    impact: { flight_id: "F1", status: "direct", direct_rule_ids: ["WX1"], propagation_sources: [] },
    recovered: { status: "operated", recovered_origin: "AAA", recovered_destination: "BBB", recovered_dep: "2026-01-01T01:10:00Z", recovered_arr: "2026-01-01T02:10:00Z" },
    changed: true, change_flags: ["time_changed"], primary_change: "time_changed", resources: {}, passenger_group_ids: [],
  }],
  propagation_edges: [{ source_flight_id: "F1", target_flight_id: "F2", resource_type: "aircraft", resource_id: "A1" }],
  aircraft: [], crew: [], passengers: [], capacity: { baseline: [], effective: [], recovered: [] }, objective: null, cost_items: [], delay_distribution: [], recovery_actions: [],
};

describe("visualization chart semantics", () => {
  it("draws disruption windows only in impact mode", () => {
    const impact = flightNetworkOption(model, "impact", model.flights, null, "light") as { series: Array<{ name?: string }> };
    const original = flightNetworkOption(model, "original", model.flights, null, "light") as { series: Array<{ name?: string }> };
    expect(impact.series.some((item) => item.name?.startsWith("扰动时域"))).toBe(true);
    expect(original.series.some((item) => item.name?.startsWith("扰动时域"))).toBe(false);
  });

  it.each(["light", "dark"] as const)("uses the shared readable grid in %s mode", (theme) => {
    const option = flightNetworkOption(model, "original", model.flights, null, theme) as {
      textStyle: { fontSize: number };
      xAxis: { axisLabel: { fontSize: number }; splitLine: { show: boolean }; minorSplitLine: { show: boolean } };
      yAxis: { axisLabel: { fontSize: number }; splitLine: { show: boolean }; splitArea: { show: boolean } };
    };
    expect(option.textStyle.fontSize).toBeGreaterThanOrEqual(12);
    expect(option.xAxis.axisLabel.fontSize).toBeGreaterThanOrEqual(12);
    expect(option.yAxis.axisLabel.fontSize).toBeGreaterThanOrEqual(12);
    expect(option.xAxis.splitLine.show).toBe(true);
    expect(option.xAxis.minorSplitLine.show).toBe(true);
    expect(option.yAxis.splitLine.show).toBe(true);
    expect(option.yAxis.splitArea.show).toBe(true);
  });

  it("keeps the evidence graph explicit and local", () => {
    const option = propagationOption(model, "F1", "light") as { series: Array<{ data: Array<{ name: string }>; links: unknown[] }> };
    expect(option.series[0].data.map((item) => item.name)).toEqual(expect.arrayContaining(["F1", "F2", "aircraft:A1"]));
    expect(option.series[0].links).toHaveLength(2);
  });

  it("carries direct exposure into resource gantt segments", () => {
    const aircraft = [{ aircraft_id: "A1", original_segments: [{ flight_id: "F1", segment_type: "flight", start_time: "2026-01-01T01:00:00Z", end_time: "2026-01-01T02:00:00Z" }], recovered_segments: [] }];
    const option = ganttOption({ ...model, aircraft }, "aircraft", "impact", "light") as { series: Array<{ data: Array<{ itemStyle: { color: string } }> }> };
    expect(option.series[0].data[0].itemStyle.color).toBe("#b4232d");
  });

  it("builds a 500-flight canvas model without DOM-per-flight rendering", () => {
    const flights = Array.from({ length: 500 }, (_, index) => ({
      ...model.flights[0],
      flight_id: `F${index}`,
      original: {
        ...model.flights[0].original,
        sched_dep: new Date(Date.parse("2026-01-01T00:00:00Z") + index * 60_000).toISOString(),
        sched_arr: new Date(Date.parse("2026-01-01T01:00:00Z") + index * 60_000).toISOString(),
      },
      impact: { ...model.flights[0].impact, flight_id: `F${index}` },
    }));
    const started = performance.now();
    const option = flightNetworkOption({ ...model, flights }, "impact", flights, null, "light") as { series: Array<{ data?: unknown[] }> };
    expect(performance.now() - started).toBeLessThan(1_000);
    expect(option.series.flatMap((item) => item.data ?? []).length).toBeGreaterThanOrEqual(500);
  });
});
