const escapeHtml = (value) => String(value ?? "—")
  .replaceAll("&", "&amp;").replaceAll("<", "&lt;")
  .replaceAll(">", "&gt;").replaceAll('"', "&quot;");

const stamp = (value) => value ? new Date(value).toLocaleString("zh-CN", { timeZone: "UTC", hour12: false }) + " UTC" : "—";
const number = (value) => value === null || value === undefined ? "—" : Number(value).toLocaleString("zh-CN", { maximumFractionDigits: 2 });
const cell = (value) => `<td>${escapeHtml(value)}</td>`;

export function renderRecovery(container, scenario, result, mode = "recovered", sortDelay = false, resultStale = false) {
  if (!result) {
    container.innerHTML = resultStale
      ? '<section class="recovery-card recovery-stale"><h2>Recovered Result is stale</h2><p>Inputs changed after the last solve. Run Solve again before reviewing or exporting Recovery.</p></section>'
      : '<p class="muted">加载完整 Solve Bundle 后点击 Solve。Scenario-only 不会生成优化结果。</p>';
    return;
  }
  const metadata = result.run_metadata;
  const diag = result.diagnostics;
  if (result.status !== "optimal") {
    container.innerHTML = `<section class="recovery-card"><h2>Solver status: ${escapeHtml(result.status)}</h2><p>${escapeHtml(diag.terminal_reason)}</p><p>没有可展示的恢复航班；此状态不代表伪造的优化方案。</p><p>Runtime ${number(metadata.runtime_seconds)} s</p></section>`;
    return;
  }
  const metrics = result.metrics.recovery;
  const totals = [
    ["Status", result.status], ["Total Cost", result.objective.total],
    ["Schedule Cost", result.objective.schedule], ["Aircraft Cost", result.objective.aircraft],
    ["Crew Cost", result.objective.crew], ["Passenger Cost", result.objective.passenger],
    ["Changed Flights", result.resolved_flights.filter((item) => item.resolved.status === "cancelled"
      || item.resolved.recovered_origin !== item.original.origin
      || item.resolved.recovered_destination !== item.original.destination
      || (item.resolved.departure_delay_minutes || 0) > 0
      || item.resolved.aircraft_id !== scenario.flights.find((flight) => flight.flight_id === item.resolved.flight_id)?.original_aircraft
      || item.resolved.crew_id !== scenario.flights.find((flight) => flight.flight_id === item.resolved.flight_id)?.original_crew).length],
    ["Cancelled", metrics.cancelled_flights],
    ["Delayed", metrics.delayed_flights], ["Mean Dep Delay", result.metrics.mean_departure_delay_minutes],
    ["Max Dep Delay", result.metrics.max_departure_delay_minutes],
    ["Aircraft Reassignments", metrics.aircraft_reassignments],
    ["Crew Reassignments", metrics.crew_reassignments],
    ["Passenger Delay (weighted)", metrics.passenger_delay_minutes_weighted],
    ["Unserved Passengers", metrics.unserved_passengers],
    ["Runtime (s)", metadata.runtime_seconds], ["Lower Bound", diag.lower_bound],
    ["Upper Bound", diag.upper_bound], ["Final Gap", diag.gap],
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
    const recoveredOD = flight.status === "cancelled" ? "CANCELLED" : `${flight.recovered_origin} → ${flight.recovered_destination}`;
    const displayOD = mode === "original" || mode === "disrupted" ? originalOD : recoveredOD;
    const impact = impacts.get(flight.flight_id);
    const riskLabel = impact?.status === "direct" ? "direct exposure"
      : impact?.status === "downstream" ? "downstream risk" : "no identified exposure";
    return `<tr class="${flight.status === "cancelled" ? "recovery-cancelled" : changed(item) ? "recovery-changed" : ""}">${[
      flight.flight_id, originalOD, displayOD, stamp(original.dep),
      mode === "original" || mode === "disrupted" ? stamp(original.dep) : stamp(flight.recovered_dep),
      stamp(original.arr), mode === "original" || mode === "disrupted" ? stamp(original.arr) : stamp(flight.recovered_arr),
      mode === "original" || mode === "disrupted" ? "—" : flight.departure_delay_minutes,
      mode === "original" || mode === "disrupted" ? "—" : flight.arrival_delay_minutes,
      mode === "original" ? "original" : mode === "disrupted" ? riskLabel : flight.status,
      mode === "original" || mode === "disrupted" ? scenario.flights.find((f) => f.flight_id === flight.flight_id)?.original_aircraft : flight.aircraft_id,
      mode === "original" || mode === "disrupted" ? scenario.flights.find((f) => f.flight_id === flight.flight_id)?.original_crew : flight.crew_id,
    ].map(cell).join("")}</tr>`;
  }).join("");
  const aircraftRows = result.aircraft_outcomes.map((item) => `<tr>${[
    item.aircraft_id, item.original_flight_ids.join(" → ") || "Idle",
    item.recovered_flight_ids.join(" → ") || "Idle", item.ferry_legs.join(", ") || "—",
    item.reassignment_count, item.final_station,
  ].map(cell).join("")}</tr>`).join("");
  const crewRows = result.crew_outcomes.map((item) => `<tr>${[
    item.crew_id, item.original_flight_ids.join(" → ") || "Idle",
    item.operated_flights.join(" → ") || "Idle",
    item.deadhead_flights.join(" → ") || "—", item.reassignment_count, item.final_station,
  ].map(cell).join("")}</tr>`).join("");
  const passengerRows = result.passenger_outcomes.map((item) => `<tr>${[
    item.outcome.pax_group_id, item.count, item.original_itinerary.join(" → "),
    item.recovered_itinerary.join(" → ") || "—", item.outcome.status,
    item.outcome.arrival_delay_minutes, item.outcome.unserved_count,
  ].map(cell).join("")}</tr>`).join("");
  const cards = totals.map(([label, value]) => `<div class="recovery-stat"><span>${escapeHtml(label)}</span><strong>${typeof value === "number" ? number(value) : escapeHtml(value)}</strong></div>`).join("");
  const table = (headers, rows) => `<div class="recovery-scroll"><table><thead><tr>${headers.map((h) => `<th>${escapeHtml(h)}</th>`).join("")}</tr></thead><tbody>${rows}</tbody></table></div>`;
  container.innerHTML = `
    <section class="recovery-card"><p class="section-kicker">EXACT SOLVER · ${escapeHtml(result.status.toUpperCase())}</p><h2>Recovery summary</h2><div class="recovery-stats">${cards}</div></section>
    <section class="recovery-card"><div class="recovery-card-head"><h2>Flight recovery</h2><button id="sort-recovery-delay" class="button small">${sortDelay ? "Original order" : "Sort by delay"}</button></div><p class="muted">${escapeHtml(mode)} · changed O-D and cancelled flights are highlighted. Disrupted mode shows exposure, not a solver decision.</p>${table(["Flight", "Original OD", "Shown OD", "Original Dep", "Shown Dep", "Original Arr", "Shown Arr", "Dep Delay", "Arr Delay", "Status", "Aircraft", "Crew"], flightRows)}</section>
    <section class="recovery-card"><h2>Aircraft · Original vs Recovered</h2>${table(["Aircraft", "Original Rotation", "Recovered Rotation", "Ferry", "Reassignments", "Final Station"], aircraftRows)}</section>
    <section class="recovery-card"><h2>Crew · OPERATE / DEADHEAD</h2>${table(["Crew", "Original Pairing", "OPERATE", "DEADHEAD", "Reassignments", "Terminal"], crewRows)}</section>
    <section class="recovery-card"><h2>Passenger recovery</h2>${table(["Group", "Count", "Original Itinerary", "Recovered Itinerary", "Status", "Arrival Delay", "Unserved"], passengerRows)}</section>
    <details class="recovery-card"><summary>Algorithm diagnostics</summary><div class="recovery-stats">${[
      ["Algorithm", diag.algorithm], ["LB", diag.lower_bound], ["UB", diag.upper_bound], ["Gap", diag.gap],
      ["Benders iterations", diag.benders_master_iterations], ["Visited schedules", diag.visited_schedules],
      ["LP cuts", diag.lp_cuts], ["Exact cuts", diag.exact_integer_cuts], ["Feasibility cuts", diag.feasibility_cuts],
      ["Aircraft columns", diag.aircraft_generated_columns], ["Crew pairings", diag.crew_generated_pairings],
      ["Aircraft B&P nodes", diag.aircraft_bp_nodes], ["Crew B&P nodes", diag.crew_bp_nodes],
      ["Integrated audit", diag.integrated_audit_pass ? "PASS" : "FAIL"],
    ].map(([label, value]) => `<div class="recovery-stat"><span>${escapeHtml(label)}</span><strong>${escapeHtml(value)}</strong></div>`).join("")}</div></details>`;
}
import { deriveFlightImpacts } from "./visualization.js";
