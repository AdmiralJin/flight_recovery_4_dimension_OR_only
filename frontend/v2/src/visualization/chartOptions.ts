import type { EChartsOption } from "echarts";
import type { JsonObject, VisualizationFlight, VisualizationMode, VisualizationModel } from "../types";

const colors = {
  normal: "#20c7a6",
  direct: "#ee6b72",
  downstream: "#f2b84b",
  cancelled: "#ee6b72",
  od_changed: "#c77cff",
  time_changed: "#f2b84b",
  aircraft_reassigned: "#5594dc",
  crew_reassigned: "#66c7d9",
  unchanged: "#20c7a6",
  ghost: "#78909c",
  ground: "#365361",
  ferry: "#c77cff",
  operate: "#20c7a6",
  deadhead: "#5594dc",
  rest: "#78909c",
  ground_transfer: "#f2b84b",
  surface: "#f2b84b",
  flight: "#20c7a6",
};

const axis = { axisLabel: { color: "#8ca4b0" }, axisLine: { lineStyle: { color: "#294653" } }, splitLine: { lineStyle: { color: "#173440" } } };
const animation = !window.matchMedia("(prefers-reduced-motion: reduce)").matches;

export function flightNetworkOption(model: VisualizationModel, mode: VisualizationMode, flights: VisualizationFlight[], selectedId: string | null): EChartsOption {
  const airports = [...new Set(flights.flatMap((item) => [String(item.original.origin), String(item.original.destination), ...(item.recovered ? [String(item.recovered.recovered_origin ?? ""), String(item.recovered.recovered_destination ?? "")] : [])].filter(Boolean)))];
  const lineData: JsonObject[] = [];
  const cancelled: JsonObject[] = [];
  for (const flight of flights) {
    const original = flight.original;
    const recovered = flight.recovered;
    if (mode === "original" || mode === "impact" || mode === "delta") {
      const state = mode === "impact" ? flight.impact.status : mode === "delta" ? "ghost" : "normal";
      lineData.push(lineItem(flight.flight_id, original, state, selectedId, mode === "delta", airports));
    }
    if ((mode === "recovered" || mode === "delta") && recovered) {
      if (recovered.status === "cancelled") {
        cancelled.push({ name: flight.flight_id, value: [Date.parse(String(original.sched_dep)), airports.indexOf(String(original.origin))], entityId: flight.flight_id, entityType: "flight" });
      } else {
        lineData.push(lineItem(flight.flight_id, {
          origin: recovered.recovered_origin,
          destination: recovered.recovered_destination,
          sched_dep: recovered.recovered_dep,
          sched_arr: recovered.recovered_arr,
        }, flight.primary_change, selectedId, false, airports));
      }
    }
  }
  const disruptionData = mode === "impact" ? model.disruptions.map((item) => ({
    value: [airports.indexOf(String(item.airport_id)), Date.parse(String(item.start_time)), Date.parse(String(item.end_time)), String(item.rule_type), String(item.direction)],
    entityId: String(item.rule_id), entityType: "capacity",
  })) : [];
  const emphasizeAlignment = mode === "impact";
  return {
    animation,
    backgroundColor: "transparent",
    aria: { enabled: true, description: `${mode} 机场 UTC 时间航班箭头图` },
    tooltip: { trigger: "item", formatter: flightTooltip },
    grid: emphasizeAlignment
      ? { left: 104, right: 38, top: 42, bottom: 76 }
      : { left: 88, right: 32, top: 30, bottom: 72 },
    xAxis: emphasizeAlignment ? {
      type: "time",
      name: "时间（UTC）",
      nameLocation: "end",
      nameGap: 12,
      nameTextStyle: { color: "#c8d9df", fontSize: 11, fontWeight: 600 },
      splitNumber: 10,
      minInterval: 10 * 60 * 1_000,
      axisLine: { show: true, lineStyle: { color: "#587480", width: 1.2 } },
      axisTick: { show: true, length: 6, lineStyle: { color: "#6f8b96" } },
      axisLabel: { show: true, color: "#c8d9df", fontSize: 11, margin: 12, formatter: timeLabel, hideOverlap: true },
      splitLine: { show: true, lineStyle: { color: "rgba(125, 157, 169, .30)", width: 1, type: "dashed" } },
      minorTick: { show: true, splitNumber: 2, lineStyle: { color: "rgba(111, 139, 150, .55)" } },
      minorSplitLine: { show: true, lineStyle: { color: "rgba(103, 137, 149, .10)", width: 1 } },
    } : { type: "time", name: "UTC", splitNumber: 7, minInterval: 10 * 60 * 1_000, ...axis, axisLabel: { color: "#8ca4b0", formatter: timeLabel, hideOverlap: true } },
    yAxis: emphasizeAlignment ? {
      type: "category",
      name: "机场",
      nameLocation: "end",
      nameGap: 14,
      nameTextStyle: { color: "#c8d9df", fontSize: 11, fontWeight: 600, align: "right" },
      data: airports,
      inverse: true,
      axisLine: { show: true, lineStyle: { color: "#587480", width: 1.2 } },
      axisTick: { show: true, alignWithLabel: true, length: 7, lineStyle: { color: "#6f8b96" } },
      axisLabel: { show: true, color: "#dbe8ec", fontSize: 12, fontWeight: 600, margin: 14 },
      splitLine: { show: true, lineStyle: { color: "rgba(125, 157, 169, .26)", width: 1 } },
      splitArea: { show: true, areaStyle: { color: ["rgba(18, 49, 60, .18)", "rgba(18, 49, 60, .04)"] } },
    } : { type: "category", data: airports, inverse: true, ...axis },
    dataZoom: [{ type: "inside", filterMode: "none" }, { type: "slider", bottom: 18, height: 22, borderColor: "#294653", textStyle: { color: "#8ca4b0" } }],
    series: [
      ...(disruptionData.length ? [{ name: "扰动时域 [start, end)", type: "custom", silent: false, renderItem: renderDisruption as never, encode: { x: [1, 2], y: 0 }, data: disruptionData, z: 1 }] : []),
      { name: "航班", type: "custom", coordinateSystem: "cartesian2d", renderItem: renderFlight as never, encode: { x: [0, 2], y: [1, 3] }, data: lineData, z: 4 },
      { name: "取消", type: "scatter", symbol: "path://M-6,-6L6,6M6,-6L-6,6", symbolSize: 18, itemStyle: { color: colors.cancelled }, data: cancelled, z: 6 },
    ],
  } as EChartsOption;
}

function lineItem(flightId: string, leg: JsonObject, state: string, selectedId: string | null, ghost: boolean, airports: string[]): JsonObject {
  const color = colors[state as keyof typeof colors] ?? colors.normal;
  return {
    name: flightId,
    entityId: flightId,
    entityType: "flight",
    state,
    value: [Date.parse(String(leg.sched_dep)), airports.indexOf(String(leg.origin)), Date.parse(String(leg.sched_arr)), airports.indexOf(String(leg.destination)), flightId, state, selectedId === flightId ? 1 : 0, ghost ? 1 : 0],
    itemStyle: { color },
  };
}

function renderFlight(_params: unknown, api: { value: (index: number) => number | string; coord: (value: [number, number]) => [number, number] }) {
  const start = api.coord([Number(api.value(0)), Number(api.value(1))]);
  const end = api.coord([Number(api.value(2)), Number(api.value(3))]);
  const label = String(api.value(4));
  const state = String(api.value(5));
  const selected = Number(api.value(6)) === 1;
  const ghost = Number(api.value(7)) === 1;
  const color = colors[state as keyof typeof colors] ?? colors.normal;
  const dx = end[0] - start[0]; const dy = end[1] - start[1]; const length = Math.max(Math.hypot(dx, dy), 1);
  const ux = dx / length; const uy = dy / length; const px = -uy; const py = ux;
  const arrowBaseX = end[0] - ux * 10; const arrowBaseY = end[1] - uy * 10;
  const width = selected ? 5 : ghost ? 1.5 : state === "direct" ? 4 : 2.4;
  return { type: "group", children: [
    { type: "line", shape: { x1: start[0], y1: start[1], x2: end[0], y2: end[1] }, style: { stroke: color, lineWidth: width, opacity: ghost ? 0.42 : 0.95, lineDash: ghost || state === "downstream" ? [6, 5] : undefined } },
    { type: "circle", shape: { cx: start[0], cy: start[1], r: selected ? 5 : 3.5 }, style: { fill: color, opacity: ghost ? 0.42 : 1 } },
    { type: "polygon", shape: { points: [[end[0], end[1]], [arrowBaseX + px * 4, arrowBaseY + py * 4], [arrowBaseX - px * 4, arrowBaseY - py * 4]] }, style: { fill: color, opacity: ghost ? 0.42 : 1 } },
    { type: "text", style: { x: (start[0] + end[0]) / 2, y: (start[1] + end[1]) / 2 - 8, text: label, fill: "#dce9ef", font: "10px ui-monospace", align: "center" } },
  ] };
}

function flightTooltip(params: unknown) {
  const value = params as { name?: string; data?: JsonObject; seriesName?: string };
  const data = value.data ?? {};
  if (value.seriesName?.startsWith("扰动")) return `<strong>${String(data.entityId)}</strong><br/>扰动时域采用 [start, end) 语义`;
  return `<strong>${value.name ?? "航班"}</strong><br/>${String(data.state ?? value.seriesName ?? "")}`;
}

function renderDisruption(params: { dataIndex: number; coordSys: { x: number; y: number; width: number; height: number } }, api: { value: (index: number) => number; coord: (value: [number, number]) => [number, number]; size: (value: [number, number]) => [number, number] }) {
  const lane = api.value(0);
  const start = api.coord([api.value(1), lane]);
  const end = api.coord([api.value(2), lane]);
  const height = Math.max(24, Math.abs(api.size([0, 1])[1]) * 0.7);
  return { type: "rect", shape: { x: start[0], y: start[1] - height / 2, width: Math.max(2, end[0] - start[0]), height }, style: { fill: "rgba(238,107,114,.18)", stroke: "#ee6b72", lineWidth: 1, lineDash: [4, 3] } };
}

export function ganttOption(model: VisualizationModel, view: "aircraft" | "crew" | "passengers", mode: VisualizationMode): EChartsOption {
  const source = model[view] as JsonObject[];
  const laneKey = view === "aircraft" ? "aircraft_id" : view === "crew" ? "crew_id" : "pax_group_id";
  const lanes = source.map((item) => String(item[laneKey]));
  const data: JsonObject[] = [];
  const flightById = new Map(model.flights.map((item) => [item.flight_id, item]));
  source.forEach((row, lane) => {
    const sets: Array<{ segments: JsonObject[]; track: number; ghost: boolean; recovered: boolean }> = [];
    if (view === "aircraft") {
      if (["original", "impact", "delta"].includes(mode)) sets.push({ segments: row.original_segments as JsonObject[], track: mode === "delta" ? -1 : 0, ghost: mode === "delta", recovered: false });
      if (["recovered", "delta"].includes(mode)) sets.push({ segments: row.recovered_segments as JsonObject[], track: mode === "delta" ? 1 : 0, ghost: false, recovered: true });
    } else if (view === "crew") {
      if (["original", "impact", "delta"].includes(mode)) sets.push({ segments: flattenDuties(row.original_duties), track: mode === "delta" ? -1 : 0, ghost: mode === "delta", recovered: false });
      if (["recovered", "delta"].includes(mode)) sets.push({ segments: flattenDuties(row.recovered_duties), track: mode === "delta" ? 1 : 0, ghost: false, recovered: true });
    } else {
      if (["original", "impact", "delta"].includes(mode)) sets.push({ segments: row.original_segments as JsonObject[], track: mode === "delta" ? -1 : 0, ghost: mode === "delta", recovered: false });
      if (["recovered", "delta"].includes(mode)) sets.push({ segments: row.recovered_segments as JsonObject[], track: mode === "delta" ? 1 : 0, ghost: false, recovered: true });
    }
    sets.forEach(({ segments, track, ghost, recovered }) => segments?.forEach((segment) => {
      if (!segment.start_time || !segment.end_time) return;
      const flight = flightById.get(String(segment.flight_id ?? ""));
      const kind = ghost ? "ghost"
        : mode === "impact" && flight ? flight.impact.status
        : recovered && view === "aircraft" && flight ? flight.primary_change
        : String(segment.segment_type ?? segment.state ?? "flight");
      data.push({
        value: [lane, Date.parse(String(segment.start_time)), Date.parse(String(segment.end_time)), track, String(segment.flight_id ?? segment.segment_type ?? "")],
        entityId: String(segment.flight_id ?? row[laneKey]), entityType: segment.flight_id ? "flight" : view === "passengers" ? "passenger" : view.slice(0, -1),
        segment,
        itemStyle: { color: colors[kind as keyof typeof colors] ?? colors.normal, opacity: ghost ? 0.35 : 0.95 },
      });
    }));
  });
  return {
    animation,
    aria: { enabled: true, description: `${view} ${mode} UTC 甘特图` },
    tooltip: { formatter: (params: unknown) => ganttTooltip(params) },
    grid: { left: 112, right: 28, top: 24, bottom: 70 },
    xAxis: { type: "time", name: "UTC", splitNumber: 7, minInterval: 10 * 60 * 1_000, ...axis, axisLabel: { color: "#8ca4b0", formatter: timeLabel, hideOverlap: true } },
    yAxis: { type: "category", data: lanes, inverse: true, ...axis },
    dataZoom: [{ type: "inside" }, { type: "slider", bottom: 16, height: 22, textStyle: { color: "#8ca4b0" } }],
    series: [{ type: "custom", renderItem: renderGantt as never, encode: { x: [1, 2], y: 0 }, data }],
  } as EChartsOption;
}

function flattenDuties(value: unknown): JsonObject[] {
  return Array.isArray(value) ? value.flatMap((item) => Array.isArray((item as JsonObject).segments) ? (item as JsonObject).segments as JsonObject[] : []) : [];
}

function renderGantt(_params: unknown, api: { value: (index: number) => number | string; coord: (value: [number, number]) => [number, number]; size: (value: [number, number]) => [number, number]; style: () => JsonObject }) {
  const lane = Number(api.value(0));
  const start = api.coord([Number(api.value(1)), lane]);
  const end = api.coord([Number(api.value(2)), lane]);
  const track = Number(api.value(3));
  const height = Math.max(8, Math.min(18, Math.abs(api.size([0, 1])[1]) * 0.28));
  const y = start[1] - height / 2 + track * (height * 0.62);
  const width = Math.max(3, end[0] - start[0]);
  const label = String(api.value(4) ?? "");
  return { type: "group", children: [
    { type: "rect", shape: { x: start[0], y, width, height }, style: { ...api.style(), stroke: "rgba(220,233,239,.35)", lineWidth: 1 } },
    ...(width > 46 && label ? [{ type: "text", style: { x: start[0] + 4, y: y + height / 2, text: label, fill: "#e7f3f6", font: "10px ui-monospace", verticalAlign: "middle", width: width - 8, overflow: "truncate" } }] : []),
  ] };
}

function ganttTooltip(params: unknown) {
  const data = (params as { data?: JsonObject }).data ?? {};
  const segment = data.segment as JsonObject | undefined;
  if (!segment) return "";
  return `<strong>${String(segment.flight_id ?? segment.segment_type ?? "航段")}</strong><br/>${String(segment.origin ?? "—")} → ${String(segment.destination ?? "—")}<br/>${formatUtc(segment.start_time)} – ${formatUtc(segment.end_time)} UTC`;
}

export function capacityOption(model: VisualizationModel, mode: VisualizationMode, movement: "departure" | "arrival"): EChartsOption {
  const set = mode === "original" ? "baseline" : mode === "impact" ? "effective" : mode === "recovered" ? "recovered" : "recovered";
  const rows = model.capacity[set] ?? [];
  const airports = [...new Set(rows.map((row) => String(row.airport_id)))];
  const intervals = [...new Set(rows.map((row) => `${String(row.start_time).slice(5, 16).replace("T", " ")}`))];
  const data = rows.map((row) => {
    const capacity = Number(row[`${movement}_capacity`] ?? 0);
    const load = Number(row[`${movement}_load`] ?? 0);
    return { value: [intervals.indexOf(String(row.start_time).slice(5, 16).replace("T", " ")), airports.indexOf(String(row.airport_id)), capacity ? load / capacity : load ? 2 : 0, load, capacity], entityId: `${String(row.airport_id)}:${String(row.start_time)}`, entityType: "capacity" };
  });
  return {
    animation,
    aria: { enabled: true, description: `${mode} ${movement} 机场容量热力图` },
    tooltip: { formatter: (params: unknown) => { const value = (params as { value?: number[] }).value ?? []; return `负荷 ${value[3] ?? 0} / 容量 ${value[4] ?? 0}<br/>利用率 ${Number(value[2] ?? 0).toFixed(2)}`; } },
    grid: { left: 82, right: 36, top: 28, bottom: 88 },
    xAxis: { type: "category", data: intervals, ...axis, axisLabel: { color: "#8ca4b0", rotate: 35 } },
    yAxis: { type: "category", data: airports, inverse: true, ...axis },
    visualMap: { min: 0, max: 1.5, calculable: true, orient: "horizontal", left: "center", bottom: 4, textStyle: { color: "#8ca4b0" }, inRange: { color: ["#123c42", "#20c7a6", "#f2b84b", "#ee6b72"] } },
    dataZoom: [{ type: "inside", xAxisIndex: 0 }, { type: "slider", xAxisIndex: 0, bottom: 50, height: 18 }],
    series: [{ type: "heatmap", data, label: { show: rows.length < 80, formatter: (params: unknown) => { const value = (params as { value?: number[] }).value ?? []; return `${value[3]}/${value[4]}`; }, color: "#e9f4f6", fontSize: 9 } }],
  } as EChartsOption;
}

export function propagationOption(model: VisualizationModel, selectedFlightId: string | null): EChartsOption {
  const relevant = selectedFlightId ? model.propagation_edges.filter((edge) => edge.source_flight_id === selectedFlightId || edge.target_flight_id === selectedFlightId) : model.propagation_edges.slice(0, 60);
  const nodes = new Map<string, JsonObject>();
  const links: JsonObject[] = [];
  relevant.forEach((edge) => {
    const source = String(edge.source_flight_id); const target = String(edge.target_flight_id); const resource = `${String(edge.resource_type)}:${String(edge.resource_id)}`;
    nodes.set(source, { name: source, entityId: source, entityType: "flight", category: 0, symbolSize: source === selectedFlightId ? 34 : 24 });
    nodes.set(target, { name: target, entityId: target, entityType: "flight", category: 2, symbolSize: target === selectedFlightId ? 34 : 24 });
    nodes.set(resource, { name: resource, entityId: String(edge.resource_id), entityType: String(edge.resource_type), category: 1, symbol: "diamond", symbolSize: 20 });
    links.push({ source, target: resource }, { source: resource, target });
  });
  return {
    animation,
    aria: { enabled: true, description: "直接暴露经飞机或机组资源序列传播到下游风险航班的证据图" },
    tooltip: { trigger: "item" },
    legend: [{ data: ["直接暴露", "资源链", "下游风险"], textStyle: { color: "#8ca4b0" } }],
    series: [{ type: "graph", layout: "force", roam: true, categories: [{ name: "直接暴露", itemStyle: { color: colors.direct } }, { name: "资源链", itemStyle: { color: colors.aircraft_reassigned } }, { name: "下游风险", itemStyle: { color: colors.downstream } }], data: [...nodes.values()], links, label: { show: true, color: "#dce9ef", fontSize: 10 }, lineStyle: { color: "source", curveness: 0.12, width: 1.5 }, force: { repulsion: 220, edgeLength: 95 } }],
  } as EChartsOption;
}

export function costOption(model: VisualizationModel): EChartsOption {
  const objective = model.objective ?? {};
  const keys = ["schedule", "aircraft", "crew", "passenger"];
  const values = keys.map((key) => Number(objective[key] ?? 0));
  let running = 0;
  const bases = values.map((value) => { const base = running; running += value; return base; });
  return { animation, aria: { enabled: true, description: "恢复目标成本瀑布图" }, tooltip: { trigger: "axis" }, grid: { left: 70, right: 30, top: 28, bottom: 54 }, xAxis: { type: "category", data: keys, ...axis }, yAxis: { type: "value", name: "成本", ...axis }, series: [{ type: "bar", stack: "total", data: bases, itemStyle: { color: "transparent" }, silent: true }, { name: "成本", type: "bar", stack: "total", data: values, itemStyle: { color: colors.normal }, label: { show: true, position: "top", color: "#dce9ef" } }] } as EChartsOption;
}

export function delayOption(model: VisualizationModel): EChartsOption {
  const rows = model.delay_distribution.filter((row) => Number(row.departure_delay_minutes ?? 0) >= 0 && Number(row.arrival_delay_minutes ?? 0) >= 0);
  return { animation, aria: { enabled: true, description: "航班起飞与到达延误分布" }, tooltip: { trigger: "axis" }, legend: { textStyle: { color: "#8ca4b0" } }, grid: { left: 66, right: 24, top: 46, bottom: 80 }, xAxis: { type: "category", data: rows.map((row) => String(row.flight_id)), ...axis, axisLabel: { color: "#8ca4b0", rotate: 40 } }, yAxis: { type: "value", name: "分钟", ...axis }, dataZoom: [{ type: "inside" }, { type: "slider", bottom: 20, height: 20 }], series: [{ name: "起飞延误", type: "bar", data: rows.map((row) => Number(row.departure_delay_minutes ?? 0)), itemStyle: { color: colors.normal } }, { name: "到达延误", type: "bar", data: rows.map((row) => Number(row.arrival_delay_minutes ?? 0)), itemStyle: { color: colors.downstream } }] } as EChartsOption;
}

function timeLabel(value: number) { const text = new Date(value).toISOString(); return text.slice(11, 16) === "00:00" ? text.slice(5, 16).replace("T", " ") : text.slice(11, 16); }
function formatUtc(value: unknown) { const parsed = Date.parse(String(value ?? "")); return Number.isFinite(parsed) ? new Date(parsed).toISOString().slice(5, 16).replace("T", " ") : "—"; }
