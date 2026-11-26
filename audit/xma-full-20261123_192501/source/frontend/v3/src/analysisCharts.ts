import type { EChartsOption } from "echarts";
import { capacityOption, costOption, delayOption, flightNetworkOption, ganttOption, propagationOption } from "../../v2/src/visualization/chartOptions";
import { chartPalette } from "../../v2/src/visualization/chartTheme";
import type { JsonObject, VisualizationFlight, VisualizationMode, VisualizationModel, VisualizationView } from "./types";
import { object, rows } from "./state";

export const stateLabels: Record<string, string> = {
  normal: "正常执行", unchanged: "未变化", direct: "直接受扰", downstream: "下游风险", cancelled: "取消", od_changed: "航线变化", time_changed: "时间变化", aircraft_reassigned: "换机", crew_reassigned: "换组", ghost: "原计划参考", ground: "地面等待", ferry: "调机", operate: "执行航段", deadhead: "机组置位", rest: "休息", ground_transfer: "地面转运", surface: "地面行程", flight: "乘机航段", recovered: "已恢复", served: "已服务", unserved: "未服务", rebooked: "改签", operated: "执行", cancelled_flight: "航班取消", transported: "已运输", partly_unserved: "部分未服务", original: "原计划",
};
const safe = (value: unknown) => String(value ?? "—").replaceAll("&", "&amp;").replaceAll("<", "&lt;").replaceAll(">", "&gt;").replaceAll('"', "&quot;").replaceAll("'", "&#39;");
const number = (value: unknown) => typeof value === "number" && Number.isFinite(value) ? value.toLocaleString("zh-CN", { maximumFractionDigits: 3 }) : "—";
const list = (value: unknown) => Array.isArray(value) ? value.length ? value.map(safe).join("、") : "无" : safe(value);
const line = (key: string, value: unknown) => `<div><span>${safe(key)}：</span>${safe(value)}</div>`;
const axisObject = (option: EChartsOption, key: "xAxis" | "yAxis"): JsonObject => object(Array.isArray(option[key]) ? option[key][0] : option[key]);
const modeLabel = (mode: VisualizationMode) => ({ original: "原计划", impact: "扰动影响", recovered: "恢复方案", delta: "变化对比" })[mode];

export function chartTime(value: unknown, timezone: string): string {
  const parsed = typeof value === "number" ? value : Date.parse(String(value ?? ""));
  if (!Number.isFinite(parsed)) return "—";
  return `${new Intl.DateTimeFormat("zh-CN", { timeZone: timezone, month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit", hourCycle: "h23" }).format(parsed)} ${timezone === "UTC" ? "UTC" : "北京时间"}`;
}

function flightDetails(flight: VisualizationFlight, timezone: string): string {
  const { original, recovered, impact } = flight;
  return `<strong>航班 ${safe(flight.flight_id)}</strong>`
    + line("原航线", `${original.origin ?? "—"} → ${original.destination ?? "—"}`)
    + line("计划起飞", chartTime(original.sched_dep, timezone)) + line("计划到达", chartTime(original.sched_arr, timezone))
    + line("原机尾 / 机组", `${original.original_aircraft ?? "—"} / ${Array.isArray(original.original_crew) ? original.original_crew.join("、") : original.original_crew ?? "—"}`)
    + line("扰动暴露", stateLabels[impact.status] ?? impact.status)
    + `<div>直接规则：${list(impact.direct_rule_ids)}</div>`
    + line("主要变化", stateLabels[flight.primary_change] ?? flight.primary_change)
    + (recovered ? line("恢复状态", stateLabels[String(recovered.status)] ?? recovered.status)
      + line("恢复航线", `${recovered.recovered_origin ?? "—"} → ${recovered.recovered_destination ?? "—"}`)
      + line("恢复起飞", chartTime(recovered.recovered_dep, timezone)) + line("恢复到达", chartTime(recovered.recovered_arr, timezone))
      + line("起飞 / 到达延误", `${number(recovered.departure_delay_minutes)} / ${number(recovered.arrival_delay_minutes)} 分钟`)
      + line("恢复机尾 / 机组", `${recovered.aircraft_id ?? "—"} / ${Array.isArray(recovered.crew_ids) ? recovered.crew_ids.join("、") : recovered.crew_id ?? "—"}`) : line("恢复方案", "当前来源未提供"))
    + `<div>关联旅客组：${list(flight.passenger_group_ids)}</div>`;
}

export function analysisTooltip(model: VisualizationModel, view: VisualizationView, mode: VisualizationMode, timezone: string, movement: "departure" | "arrival") {
  const flights = new Map(model.flights.map(flight => [flight.flight_id, flight]));
  const laneKey = view === "aircraft" ? "aircraft_id" : view === "crew" ? "crew_id" : "pax_group_id";
  const source = ["aircraft", "crew", "passengers"].includes(view) ? model[view as "aircraft" | "crew" | "passengers"] : [];
  const capacitySet = mode === "original" ? "baseline" : mode === "impact" ? "effective" : "recovered";
  const capacities = new Map((model.capacity[capacitySet] ?? []).map(row => [`${row.airport_id}:${row.start_time}`, row]));
  return (params: unknown): string => {
    const items = Array.isArray(params) ? params : [params];
    const first = object(items[0]); const data = object(first.data); const values = Array.isArray(data.value) ? data.value : [];
    if (view === "cost") {
      const index = Number(first.dataIndex ?? 0); const keys = ["schedule", "aircraft", "crew", "passenger"];
      const labels = ["航班计划", "飞机资源", "机组资源", "旅客恢复"]; const key = keys[index];
      const objective = object(model.objective); const amount = mode === "original" ? 0 : objective[key];
      const unit = objective.profile === "tianchi_2017" ? "天池评分（分）" : "AIR 研究成本";
      const total = mode === "original" ? 0 : objective.total;
      const share = typeof total === "number" && total !== 0 && typeof amount === "number" ? `${(amount / total * 100).toFixed(2)}%` : "—";
      const notes = ["航班取消、延误及适用的航线变更成本", "换机及适用的调机成本", "换组及适用的置位成本；厦航关闭机组模块", "留乘、改签延误与未服务旅客损失，口径依所选目标"];
      return `<strong>${labels[index] ?? "成本"}</strong>${line("方案", modeLabel(mode))}${line("分项", `${number(amount)} ${unit}`)}${line("运行总额", `${number(total)} ${unit}`)}${line("占比", share)}${line("含义", notes[index])}${line("统计范围", "完整运行，不随航班筛选重新计价")}${mode === "original" ? line("基线说明", "零值表示恢复增量基线，不是实际运营总成本") : ""}`;
    }
    if (view === "capacity") {
      const row = capacities.get(String(data.entityId));
      if (!row) return line("容量", "当前时间窗无证据");
      const load = row[`${movement}_load`]; const capacity = row[`${movement}_capacity`];
      return `<strong>机场 ${safe(row.airport_id)} · ${movement === "departure" ? "起飞" : "到达"}</strong>${line("开始", chartTime(row.start_time, timezone))}${line("结束（不含）", chartTime(row.end_time, timezone))}${line("负荷 / 容量", `${number(load)} / ${number(capacity)} 架次`)}${line("利用率", typeof capacity === "number" && capacity > 0 && typeof load === "number" ? `${(load / capacity * 100).toFixed(2)}%` : Number(load) > 0 ? "零容量且有负荷，超限" : "零容量、无负荷")}${line("口径", `${modeLabel(mode)}；机场全量负荷，不按航班文本筛选重算`)}`;
    }
    const flightId = view === "delay" ? String(first.axisValue ?? first.name) : String(data.entityId ?? first.name ?? "");
    const flight = flights.get(flightId);
    const segment = object(data.segment);
    const lane = source[Number(values[0])];
    let html = "";
    if (lane && Object.keys(segment).length) {
      html += `<strong>${view === "passengers" ? "旅客组" : view === "crew" ? "机组" : "飞机"} ${safe(lane[laneKey])}</strong>`;
      for (const [label, key] of [["人数", "count"], ["人数", "passenger_count"], ["人数", "size"], ["座位", "seats"], ["机型", "aircraft_type"], ["机型", "equipment_type"], ["初始机场", "initial_station"], ["期末要求机场", "required_final_station"], ["实际期末机场", "actual_final_station"], ["状态", "status"], ["恢复状态", "recovered_status"], ["到达延误（分钟）", "arrival_delay_minutes"], ["未服务人数", "unserved_count"], ["统计口径", "count_semantics"], ["原行程", "original_itinerary_id"], ["恢复行程", "recovered_itinerary_id"]]) if (lane[key] != null) html += line(label, stateLabels[String(lane[key])] ?? lane[key]);
      html += line("航段", stateLabels[String(segment.segment_type ?? segment.state)] ?? segment.segment_type ?? segment.state ?? "航段") + line("航线", `${segment.origin ?? "—"} → ${segment.destination ?? "—"}`) + line("开始", chartTime(segment.start_time, timezone)) + line("结束", chartTime(segment.end_time, timezone));
    }
    if (flight) return html + flightDetails(flight, timezone);
    if (data.entityType === "capacity") {
      const rule = model.disruptions.find(row => row.rule_id === data.entityId);
      if (rule) return `<strong>扰动 ${safe(rule.rule_id)}</strong>${line("机场", rule.airport_id)}${line("类型 / 方向", `${rule.rule_type} / ${rule.direction}`)}${line("开始", chartTime(rule.start_time, timezone))}${line("结束（不含）", chartTime(rule.end_time, timezone))}${line("容量变化", rule.capacity_change ?? rule.capacity ?? "见规则证据")}`;
    }
    if (view === "propagation") return `<strong>资源传播关联</strong>${line("实体", data.entityId ?? data.source ?? first.name)}${line("目标", data.target ?? "—")}${line("说明", "表示共享资源的风险关联，不代表因果或实际延误")}`;
    return html || line("实体", data.entityId ?? first.name ?? "未提供更多证据");
  };
}

function optionFor(model: VisualizationModel, view: VisualizationView, mode: VisualizationMode, selected: string | null, theme: "light" | "dark", movement: "departure" | "arrival") {
  if (view === "flights") return flightNetworkOption(model, mode, model.flights, selected, theme);
  if (view === "aircraft" || view === "crew" || view === "passengers") return ganttOption(model, view, mode, theme);
  if (view === "capacity") return capacityOption(model, mode, movement, theme);
  if (view === "propagation") return propagationOption(model, selected, theme);
  return view === "cost" ? costOption(model, mode, theme) : delayOption(model, mode, theme);
}

// Derive geometry and axis domains from the complete model, then mask data.
// No lane is re-indexed and no time/value extent is recomputed from a filter.
export function analysisOption(model: VisualizationModel, view: VisualizationView, mode: VisualizationMode, theme: "light" | "dark", selected: string | null, movement: "departure" | "arrival", ids: Set<string>, airport: string, timezone: string): EChartsOption {
  const option = optionFor(model, view, mode, selected, theme, movement);
  const fullSeries = Array.isArray(option.series) ? option.series : [];
  const xAxis = axisObject(option, "xAxis"); const yAxis = axisObject(option, "yAxis");
  const fullXCategories = Array.isArray(xAxis.data) ? xAxis.data : [];
  const extent: number[] = [];
  if (xAxis.type === "time") {
    for (const time of [model.time_range.start, model.time_range.end]) { const n = Date.parse(String(time ?? "")); if (Number.isFinite(n)) extent.push(n); }
    for (const flight of model.flights) for (const time of [flight.original.sched_dep, flight.original.sched_arr, flight.recovered?.recovered_dep, flight.recovered?.recovered_arr]) { const n = Date.parse(String(time ?? "")); if (Number.isFinite(n)) extent.push(n); }
    for (const series of fullSeries) for (const datum of rows(series.data)) {
      const v = Array.isArray(datum.value) ? datum.value : [];
      const indexes = view === "flights" ? datum.entityType === "capacity" ? [1, 2] : [0, 2] : [1, 2];
      for (const index of indexes) if (typeof v[index] === "number" && Number.isFinite(v[index])) extent.push(v[index] as number);
    }
    if (extent.length) {
      let min = Infinity; let max = -Infinity;
      for (const value of extent) { min = Math.min(min, value); max = Math.max(max, value); }
      xAxis.min = min; xAxis.max = Math.max(min + 60_000, max);
    }
    xAxis.name = timezone === "UTC" ? "时间（UTC）" : "时间（北京时间）";
    xAxis.axisLabel = { ...object(xAxis.axisLabel), formatter: (value: number) => chartTime(value, timezone).replace(/ (UTC|北京时间)$/, "") };
  }
  if (yAxis.type === "value") {
    const amounts = view === "cost" ? [Number(object(model.objective).total ?? 0), ...["schedule", "aircraft", "crew", "passenger"].map(key => Number(object(model.objective)[key] ?? 0))] : model.delay_distribution.flatMap(row => [Number(row.departure_delay_minutes ?? 0), Number(row.arrival_delay_minutes ?? 0)]);
    let max = 1; let min = 0;
    for (const value of amounts) if (Number.isFinite(value)) { min = Math.min(min, value); max = Math.max(max, value); }
    yAxis.min = min; yAxis.max = max * 1.12;
  }
  const categories = Array.isArray(yAxis.data) ? yAxis.data : [];
  option.series = fullSeries.map(series => {
    if (view === "cost") return series;
    if (view === "delay") return { ...series, data: (series.data as unknown[]).map((value, index) => ids.has(String(fullXCategories[index])) ? value : null) };
    if (view === "propagation") {
      const links = rows(object(series).links).filter(link => ids.has(String(link.source)) || ids.has(String(link.target)));
      const nodes = new Set(links.flatMap(link => [String(link.source), String(link.target)]));
      return { ...series, links, data: rows(series.data).filter(row => nodes.has(String(row.name))) };
    }
    return { ...series, data: rows(series.data).filter(datum => {
      if (view === "capacity") return !airport || categories[Number((datum.value as number[])[1])] === airport;
      if (datum.entityType === "flight") return ids.has(String(datum.entityId));
      if (datum.segment) return ids.size > 0;
      if (datum.entityType === "capacity") return !airport || categories[Number((datum.value as number[])[0])] === airport;
      return true;
    }) };
  }) as EChartsOption["series"];
  if (option.xAxis && option.yAxis) {
    option.xAxis = xAxis as EChartsOption["xAxis"]; option.yAxis = yAxis as EChartsOption["yAxis"];
    const sliders = Array.isArray(option.dataZoom) ? option.dataZoom : [];
    option.dataZoom = [
      { ...object(sliders.find(item => object(item).type === "inside")), id: "wb3-x-inside", type: "inside", xAxisIndex: 0, filterMode: "none" },
      { ...object(sliders.find(item => object(item).type === "slider")), id: "wb3-x-slider", type: "slider", xAxisIndex: 0, filterMode: "none", start: 0, end: 100 },
      { id: "wb3-y-slider", type: "slider", yAxisIndex: 0, orient: "vertical", right: 6, top: 42, bottom: view === "capacity" ? 132 : 82, width: 16, filterMode: "none", start: 0, end: 100, showDetail: false },
    ];
    option.grid = { ...object(option.grid), right: 62 };
  }
  if (view === "cost") {
    const series = Array.isArray(option.series) ? option.series : [];
    option.legend = { top: 0, data: series.map(row => row.name).filter(Boolean) as string[], textStyle: { color: chartPalette(theme).muted } };
    option.grid = { ...object(option.grid), top: 52 };
  }
  option.tooltip = { ...object(option.tooltip), confine: true, enterable: true, extraCssText: "max-width:460px;max-height:65vh;overflow:auto;white-space:normal;line-height:1.75", formatter: analysisTooltip(model, view, mode, timezone, movement) };
  return option;
}

export function chartLegend(view: VisualizationView, theme: "light" | "dark") {
  const palette = chartPalette(theme);
  const keys = view === "flights" || view === "aircraft" ? ["normal", "direct", "downstream", "cancelled", "time_changed", "od_changed", "aircraft_reassigned", "crew_reassigned", "ghost", ...(view === "aircraft" ? ["ground", "ferry"] : [])] : view === "crew" ? ["operate", "deadhead", "rest", "ground_transfer", "direct", "downstream", "ghost"] : view === "passengers" ? ["flight", "surface", "ground", "direct", "downstream", "ghost"] : [];
  return keys.map(key => ({ key, label: stateLabels[key], color: palette[key as keyof typeof palette], dashed: key === "ghost" || key === "downstream" }));
}
