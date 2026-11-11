import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { describe, expect, it } from "vitest";
import { analysisOption, analysisTooltip, chartLegend } from "./analysisCharts";
import { object, rows } from "./state";
import type { VisualizationModel, VisualizationView } from "./types";

const fixture = JSON.parse(readFileSync(resolve(process.cwd(), "../.workbench/v3_acceptance/api-fixtures.json"), "utf8"));
const model: VisualizationModel = fixture.air.visualization;
const ids = new Set(model.flights.map(flight => flight.flight_id));
const get = (view: VisualizationView, selected = ids, airport = "") => analysisOption(model, view, "recovered", "light", null, "departure", selected, airport, "UTC");
const axis = (value: unknown) => { const a = object(Array.isArray(value) ? value[0] : value); return { min: a.min, max: a.max, data: a.data }; };

describe("analysis invariants", () => {
  for (const view of ["flights", "aircraft", "crew", "passengers", "capacity", "cost", "delay"] as const) it(`${view}: narrowing and emptying the filter preserves both axis domains`, () => {
    const baseline = get(view);
    for (const filtered of [get(view, new Set([model.flights[0].flight_id]), "A"), get(view, new Set(), "NO_MATCH")]) {
      expect(axis(filtered.xAxis)).toEqual(axis(baseline.xAxis));
      expect(axis(filtered.yAxis)).toEqual(axis(baseline.yAxis));
    }
  });
  it("filtered flight coordinates still use the full airport lanes and empty search draws no flights", () => {
    const filtered = get("flights", new Set([model.flights[0].flight_id]));
    const data = rows(rows(filtered.series).find(series => series.name === "航班")?.data);
    expect(data).toHaveLength(1);
    expect(data[0].entityId).toBe(model.flights[0].flight_id);
    expect(rows(get("flights", new Set()).series).flatMap(series => rows(series.data))).toHaveLength(0);
  });
  it("flight and passenger hover explains both plans, delays, resource and group counts", () => {
    const flight = model.flights.find(row => row.recovered?.departure_delay_minutes)!;
    const html = analysisTooltip(model, "flights", "delta", "UTC", "departure")({ data: { entityId: flight.flight_id } });
    for (const text of [flight.flight_id, "计划起飞", "恢复起飞", "起飞 / 到达延误", "原机尾", "直接规则", "关联旅客组"]) expect(html).toContain(text);
    const passenger = model.passengers[0];
    const segment = rows(passenger.original_segments)[0];
    const tip = analysisTooltip(model, "passengers", "original", "UTC", "departure")({ data: { value: [0], segment, entityId: segment.flight_id } });
    expect(tip).toContain("旅客组"); expect(tip).toContain(String(passenger.count)); expect(tip).toContain("未服务人数");
  });
  it("capacity tooltip shows the exact window, direction, load and capacity", () => {
    const row = model.capacity.baseline[0];
    const tip = analysisTooltip(model, "capacity", "original", "UTC", "arrival")({ data: { entityId: `${row.airport_id}:${row.start_time}` } });
    for (const text of ["到达", "结束（不含）", "负荷 / 容量", String(row.arrival_capacity), "利用率"]) expect(tip).toContain(text);
  });
  it("cost hover uses a global denominator and states its scoring units", () => {
    const tip = analysisTooltip(fixture.xma.visualization, "cost", "recovered", "Asia/Shanghai", "departure")([{ dataIndex: 3 }]);
    for (const text of ["旅客恢复", "1,148", "5,948", "天池评分", "不随航班筛选"]) expect(tip).toContain(text);
  });
  it("tooltip never treats input identifiers as markup", () => {
    const modified = structuredClone(model); modified.flights[0].flight_id = '<img src=x onerror="alert(1)">';
    const tip = analysisTooltip(modified, "flights", "original", "UTC", "departure")({ data: { entityId: modified.flights[0].flight_id } });
    expect(tip).not.toContain("<img"); expect(tip).toContain("&lt;img");
  });
  it("legends cover blue aircraft reassignment, crew deadhead and all colored resource categories", () => {
    expect(chartLegend("flights", "light").some(item => item.key === "aircraft_reassigned" && item.label === "换机")).toBe(true);
    expect(chartLegend("crew", "dark").some(item => item.key === "deadhead")).toBe(true);
    expect(chartLegend("passengers", "light").some(item => item.key === "surface")).toBe(true);
  });
});
