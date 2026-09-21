const escapeHtml = (value) => String(value ?? "—")
  .replaceAll("&", "&amp;").replaceAll("<", "&lt;")
  .replaceAll(">", "&gt;").replaceAll('"', "&quot;");

const stamp = (value) => value ? new Date(value).toLocaleString("zh-CN", { timeZone: "UTC", hour12: false }) + " UTC" : "—";
const number = (value) => value === null || value === undefined ? "—" : Number(value).toLocaleString("zh-CN", { maximumFractionDigits: 2 });
const cell = (value) => `<td>${escapeHtml(value)}</td>`;
const statusDisplay = (value) => ({
  optimal: "最优（optimal）",
  infeasible: "不可行（infeasible）",
  cancelled: "取消",
  operated: "执飞",
  served: "已承运",
  unserved: "未承运",
  partial: "部分承运",
}[value] || value);
const modeDisplay = (value) => ({
  original: "原始计划",
  disrupted: "扰动 / 风险",
  recovered: "恢复方案",
  difference: "仅显示差异",
}[value] || value);

export function renderRecovery(container, scenario, result, mode = "recovered", sortDelay = false) {
  if (!result) {
    container.innerHTML = '<p class="muted">加载完整 Solve Bundle 后点击“求解”。Scenario-only 不会生成优化结果。</p>';
    return;
  }
  const metadata = result.run_metadata;
  const diag = result.diagnostics;
  if (result.status !== "optimal") {
    container.innerHTML = `<section class="recovery-card"><h2>求解器状态：${escapeHtml(statusDisplay(result.status))}</h2><p>${escapeHtml(diag.terminal_reason)}</p><p>没有可展示的恢复航班；系统不会为该状态虚构优化方案。</p><p>运行时间：${number(metadata.runtime_seconds)} 秒</p></section>`;
    return;
  }
  const metrics = result.metrics.recovery;
  const totals = [
    ["总成本", result.objective.total], ["取消航班数", metrics.cancelled_flights],
    ["延误航班数", metrics.delayed_flights], ["平均起飞延误（分钟）", result.metrics.mean_departure_delay_minutes],
    ["最大起飞延误（分钟）", result.metrics.max_departure_delay_minutes],
    ["飞机改派次数", metrics.aircraft_reassignments],
    ["机组改派次数", metrics.crew_reassignments],
    ["旅客加权延误（分钟）", metrics.passenger_delay_minutes_weighted],
    ["未承运旅客数", metrics.unserved_passengers],
    ["运行时间（秒）", metadata.runtime_seconds], ["最终 Gap", diag.gap],
  ];
  const flights = [...result.resolved_flights];
  const impacts = deriveFlightImpacts(scenario);
  if (sortDelay) flights.sort((a, b) => (b.resolved.departure_delay_minutes || 0) - (a.resolved.departure_delay_minutes || 0) || a.resolved.flight_id.localeCompare(b.resolved.flight_id));
  const changed = (item) => item.resolved.status === "cancelled"
    || item.resolved.recovered_origin !== item.original.origin
    || item.resolved.recovered_destination !== item.original.destination
    || (item.resolved.departure_delay_minutes || 0) > 0
    || item.resolved.aircraft_id !== scenario.flights.find((f) => f.flight_id === item.resolved.flight_id)?.original_aircraft
    || item.resolved.crew_id !== scenario.flights.find((f) => f.flight_id === item.resolved.flight_id)?.original_crew;
  const visible = mode === "difference" ? flights.filter(changed) : flights;
  const flightRows = visible.map((item) => {
    const flight = item.resolved;
    const original = item.original;
    const originalOD = `${original.origin} → ${original.destination}`;
    const recoveredOD = flight.status === "cancelled" ? "已取消" : `${flight.recovered_origin} → ${flight.recovered_destination}`;
    const displayOD = mode === "original" || mode === "disrupted" ? originalOD : recoveredOD;
    const impact = impacts.get(flight.flight_id);
    const riskLabel = impact?.status === "direct" ? "直接暴露"
      : impact?.status === "downstream" ? "下游传播风险" : "未识别到暴露";
    return `<tr class="${flight.status === "cancelled" ? "recovery-cancelled" : changed(item) ? "recovery-changed" : ""}">${[
      flight.flight_id, originalOD, displayOD, stamp(original.dep),
      mode === "original" || mode === "disrupted" ? stamp(original.dep) : stamp(flight.recovered_dep),
      stamp(original.arr), mode === "original" || mode === "disrupted" ? stamp(original.arr) : stamp(flight.recovered_arr),
      mode === "original" || mode === "disrupted" ? "—" : flight.departure_delay_minutes,
      mode === "original" || mode === "disrupted" ? "—" : flight.arrival_delay_minutes,
      mode === "original" ? "原始计划" : mode === "disrupted" ? riskLabel : statusDisplay(flight.status),
      mode === "original" || mode === "disrupted" ? scenario.flights.find((f) => f.flight_id === flight.flight_id)?.original_aircraft : flight.aircraft_id,
      mode === "original" || mode === "disrupted" ? scenario.flights.find((f) => f.flight_id === flight.flight_id)?.original_crew : flight.crew_id,
    ].map(cell).join("")}</tr>`;
  }).join("");
  const aircraftRows = result.aircraft_outcomes.map((item) => `<tr>${[
    item.aircraft_id, item.original_flight_ids.join(" → ") || "空闲",
    item.recovered_flight_ids.join(" → ") || "空闲", item.ferry_legs.join(", ") || "—",
    item.reassignment_count, item.final_station,
  ].map(cell).join("")}</tr>`).join("");
  const crewRows = result.crew_outcomes.map((item) => `<tr>${[
    item.crew_id, item.original_flight_ids.join(" → ") || "空闲",
    item.operated_flights.join(" → ") || "空闲",
    item.deadhead_flights.join(" → ") || "—", item.reassignment_count, item.final_station,
  ].map(cell).join("")}</tr>`).join("");
  const passengerRows = result.passenger_outcomes.map((item) => `<tr>${[
    item.outcome.pax_group_id, item.count, item.original_itinerary.join(" → "),
    item.recovered_itinerary.join(" → ") || "—", statusDisplay(item.outcome.status),
    item.outcome.arrival_delay_minutes, item.outcome.unserved_count,
  ].map(cell).join("")}</tr>`).join("");
  const cards = totals.map(([label, value]) => `<div class="recovery-stat"><span>${escapeHtml(label)}</span><strong>${number(value)}</strong></div>`).join("");
  const table = (headers, rows) => `<div class="recovery-scroll"><table><thead><tr>${headers.map((h) => `<th>${escapeHtml(h)}</th>`).join("")}</tr></thead><tbody>${rows}</tbody></table></div>`;
  container.innerHTML = `
    <section class="recovery-card"><p class="section-kicker">精确求解器 · ${escapeHtml(statusDisplay(result.status))}</p><h2>恢复结果摘要</h2><div class="recovery-stats">${cards}</div></section>
    <section class="recovery-card"><div class="recovery-card-head"><h2>航班恢复</h2><button id="sort-recovery-delay" class="button small">${sortDelay ? "恢复原始顺序" : "按延误排序"}</button></div><p class="muted">${escapeHtml(modeDisplay(mode))} · 已变更的 O-D 与取消航班将突出显示。“扰动 / 风险”模式展示的是暴露风险，并非求解器决策。</p>${table(["航班", "原始 O-D", "当前显示 O-D", "原计划起飞", "当前显示起飞", "原计划到达", "当前显示到达", "起飞延误", "到达延误", "状态", "飞机", "机组"], flightRows)}</section>
    <section class="recovery-card"><h2>飞机 · 原始轮转与恢复轮转</h2>${table(["飞机", "原始轮转", "恢复轮转", "调机 Ferry", "改派次数", "最终机场"], aircraftRows)}</section>
    <section class="recovery-card"><h2>机组 · OPERATE / DEADHEAD</h2>${table(["机组", "原始配对", "执飞 OPERATE", "加机组 DEADHEAD", "改派次数", "终到机场"], crewRows)}</section>
    <section class="recovery-card"><h2>旅客恢复</h2>${table(["旅客组", "人数", "原始行程", "恢复行程", "状态", "到达延误", "未承运人数"], passengerRows)}</section>
    <details class="recovery-card"><summary>算法诊断信息</summary><div class="recovery-stats">${[
      ["算法", diag.algorithm], ["下界 LB", diag.lower_bound], ["上界 UB", diag.upper_bound], ["Gap", diag.gap],
      ["Benders 迭代次数", diag.benders_master_iterations], ["已访问排班数", diag.visited_schedules],
      ["LP 割数量", diag.lp_cuts], ["精确整数割数量", diag.exact_integer_cuts], ["可行性割数量", diag.feasibility_cuts],
      ["飞机生成列数量", diag.aircraft_generated_columns], ["机组配对数量", diag.crew_generated_pairings],
      ["飞机 B&P 节点数", diag.aircraft_bp_nodes], ["机组 B&P 节点数", diag.crew_bp_nodes],
      ["集成审计", diag.integrated_audit_pass ? "通过" : "失败"],
    ].map(([label, value]) => `<div class="recovery-stat"><span>${escapeHtml(label)}</span><strong>${escapeHtml(value)}</strong></div>`).join("")}</div></details>`;
}
import { deriveFlightImpacts } from "./visualization.js";
