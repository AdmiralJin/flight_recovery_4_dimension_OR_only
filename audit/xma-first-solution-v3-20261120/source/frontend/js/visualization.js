const SVG_NS = "http://www.w3.org/2000/svg";
const TICK_CANDIDATES = [15, 30, 60, 120, 180, 360];

let currentModel = null;
let selectedFlightId = null;
let networkMode = "disruption";
let capacityMode = "departures";

function epoch(value) {
  return new Date(value).getTime();
}

function inHalfOpenInterval(value, start, end) {
  const time = epoch(value);
  return time >= epoch(start) && time < epoch(end);
}

function svgElement(name, attributes = {}) {
  const element = document.createElementNS(SVG_NS, name);
  for (const [key, value] of Object.entries(attributes)) {
    element.setAttribute(key, String(value));
  }
  return element;
}

function textElement(tag, text, className) {
  const element = document.createElement(tag);
  if (className) element.className = className;
  element.textContent = text;
  return element;
}

function formatUtcTime(value) {
  return new Date(value).toISOString().slice(11, 16);
}

function formatUtcDateTime(value) {
  return `${new Date(value).toISOString().slice(0, 16).replace("T", " ")} UTC`;
}

function statusLabel(status) {
  return {
    direct: "直接暴露",
    downstream: "下游传播风险",
    normal: "按当前规则判定为正常",
  }[status];
}

function recoveredStatusLabel(view) {
  if (!view?.resolved) return "缺少恢复结果";
  if (view.cancelled) return "已取消";
  const changes = [];
  if (view.odChanged) changes.push("O-D 变更");
  if (view.delayed) changes.push(`延误 +${view.resolved.departure_delay_minutes || 0} 分钟`);
  if (view.aircraftReassigned) changes.push("飞机改派");
  if (view.crewReassigned) changes.push("机组改派");
  return changes.length ? changes.join(" · ") : "按原计划执行";
}

export function classifyDisruptionType(restrictionType) {
  const value = String(restrictionType || "").toLowerCase();
  if (["closure", "closed", "airport_shutdown", "curfew"].some((token) => value.includes(token))) {
    return "both";
  }
  if (["departure", "depart", "dep_"].some((token) => value.includes(token))) {
    return "departure";
  }
  if (["arrival", "arrive", "arr_"].some((token) => value.includes(token))) {
    return "arrival";
  }
  return "unknown";
}

export function chooseTimeTickMinutes(startTime, endTime) {
  const durationMinutes = (epoch(endTime) - epoch(startTime)) / 60_000;
  return TICK_CANDIDATES.reduce((best, candidate) => {
    const bestDistance = Math.abs(durationMinutes / best - 10);
    const candidateDistance = Math.abs(durationMinutes / candidate - 10);
    return candidateDistance < bestDistance ? candidate : best;
  });
}

export function buildScenarioIndexes(scenario) {
  return {
    airportsById: new Map(scenario.airports.map((airport) => [airport.airport_id, airport])),
    flightsById: new Map(scenario.flights.map((flight) => [flight.flight_id, flight])),
    aircraftById: new Map(scenario.aircraft.map((aircraft) => [aircraft.tail_id, aircraft])),
    crewById: new Map(scenario.crew.map((crew) => [crew.crew_id, crew])),
    passengersById: new Map(scenario.passengers.map((passenger) => [passenger.pax_group_id, passenger])),
  };
}

function isDirectlyExposed(flight, disruption, type) {
  const departureMatch = flight.origin === disruption.airport
    && inHalfOpenInterval(flight.sched_dep, disruption.start_time, disruption.end_time);
  const arrivalMatch = flight.destination === disruption.airport
    && inHalfOpenInterval(flight.sched_arr, disruption.start_time, disruption.end_time);
  if (type === "departure") return departureMatch;
  if (type === "arrival") return arrivalMatch;
  if (type === "both") return departureMatch || arrivalMatch;
  return false;
}

function propagateAlongSequence(sequence, impacts, sourceType, resourceId) {
  const sourceFlightIds = [];
  for (const flightId of sequence) {
    const impact = impacts.get(flightId);
    if (!impact) continue;
    if (impact.directDisruptions.length) {
      sourceFlightIds.push(flightId);
      continue;
    }
    for (const sourceFlightId of sourceFlightIds) {
      impact.propagationSources.push({
        type: sourceType,
        resourceId,
        sourceFlightId,
      });
    }
  }
}

export function deriveFlightImpacts(scenario) {
  const impacts = new Map(scenario.flights.map((flight) => [flight.flight_id, {
    status: "normal",
    directDisruptions: [],
    propagationSources: [],
  }]));

  scenario.disruptions.forEach((disruption, disruptionIndex) => {
    const type = classifyDisruptionType(disruption.restriction_type);
    if (type === "unknown") return;
    for (const flight of scenario.flights) {
      if (isDirectlyExposed(flight, disruption, type)) {
        impacts.get(flight.flight_id).directDisruptions.push({
          disruptionIndex,
          airport: disruption.airport,
          restrictionType: disruption.restriction_type,
          type,
          startTime: disruption.start_time,
          endTime: disruption.end_time,
          capacityChange: disruption.capacity_change,
        });
      }
    }
  });

  for (const aircraft of scenario.aircraft) {
    propagateAlongSequence(aircraft.original_rotation, impacts, "aircraft", aircraft.tail_id);
  }
  for (const crew of scenario.crew) {
    propagateAlongSequence(crew.original_pairing, impacts, "crew", crew.crew_id);
  }

  for (const impact of impacts.values()) {
    if (impact.directDisruptions.length) impact.status = "direct";
    else if (impact.propagationSources.length) impact.status = "downstream";
  }
  return impacts;
}

export function derivePassengerRisk(scenario, impacts) {
  const risks = new Map();
  for (const passenger of scenario.passengers) {
    const firstAffectedIndex = passenger.original_itinerary.findIndex(
      (flightId) => {
        const impact = impacts.get(flightId);
        return impact ? impact.status !== "normal" : false;
      },
    );
    risks.set(passenger.pax_group_id, {
      atRisk: firstAffectedIndex >= 0,
      firstAffectedFlightId: firstAffectedIndex >= 0
        ? passenger.original_itinerary[firstAffectedIndex]
        : null,
      affectedFlightIds: firstAffectedIndex >= 0
        ? passenger.original_itinerary.slice(firstAffectedIndex)
        : [],
    });
  }
  return risks;
}

export function capacityStatus(load, capacity) {
  if (capacity === 0) return load === 0 ? "zero" : "over";
  if (load === 0) return "empty";
  if (load < capacity) return "within";
  if (load === capacity) return "at";
  return "over";
}

export function deriveCapacityCells(scenario, mode = "departures") {
  const isDeparture = mode === "departures";
  return scenario.airport_intervals.map((interval, intervalIndex) => {
    const load = scenario.flights.filter((flight) => {
      const stationMatches = isDeparture
        ? flight.origin === interval.airport
        : flight.destination === interval.airport;
      const time = isDeparture ? flight.sched_dep : flight.sched_arr;
      return stationMatches && inHalfOpenInterval(time, interval.start_time, interval.end_time);
    }).length;
    const capacity = isDeparture ? interval.dep_capacity : interval.arr_capacity;
    return {
      intervalIndex,
      airport: interval.airport,
      startTime: interval.start_time,
      endTime: interval.end_time,
      load,
      capacity,
      status: capacityStatus(load, capacity),
      gateCapacity: interval.gate_capacity,
      curfew: interval.curfew_flag,
      weatherRestrictions: interval.weather_restrictions,
    };
  });
}

export function deriveRecoveredFlightViews(scenario, recoveredResult) {
  const resolvedById = new Map(
    (recoveredResult?.resolved_flights || []).map((item) => {
      const resolved = item.resolved || item;
      return [resolved.flight_id, resolved];
    }),
  );
  return scenario.flights.map((flight) => {
    const resolved = resolvedById.get(flight.flight_id) || null;
    const cancelled = resolved?.status === "cancelled";
    const odChanged = Boolean(
      resolved && !cancelled
      && (resolved.recovered_origin !== flight.origin
        || resolved.recovered_destination !== flight.destination),
    );
    const delayed = Boolean(
      resolved && !cancelled
      && ((resolved.departure_delay_minutes || 0) > 0
        || (resolved.arrival_delay_minutes || 0) > 0),
    );
    const aircraftReassigned = Boolean(
      resolved && !cancelled && resolved.aircraft_id !== flight.original_aircraft,
    );
    const crewReassigned = Boolean(
      resolved && !cancelled && resolved.crew_id !== flight.original_crew,
    );
    const visualStatus = cancelled ? "cancelled"
      : odChanged ? "rerouted"
      : delayed ? "delayed"
      : aircraftReassigned || crewReassigned ? "reassigned"
      : "recovered";
    return {
      flight,
      resolved,
      cancelled,
      odChanged,
      delayed,
      aircraftReassigned,
      crewReassigned,
      changed: cancelled || odChanged || delayed || aircraftReassigned || crewReassigned,
      visualStatus,
    };
  });
}

export function deriveVisualizationModel(scenario, recoveredResult = null) {
  const impacts = deriveFlightImpacts(scenario);
  const recoveredFlights = deriveRecoveredFlightViews(scenario, recoveredResult);
  const recoveredAvailable = recoveredResult?.status === "optimal"
    && recoveredFlights.length === scenario.flights.length
    && recoveredFlights.every((item) => item.resolved);
  return {
    scenario,
    recoveredResult,
    recoveredFlights,
    recoveredByFlightId: new Map(recoveredFlights.map((item) => [item.flight.flight_id, item])),
    recoveredAvailable,
    indexes: buildScenarioIndexes(scenario),
    impacts,
    passengerRisk: derivePassengerRisk(scenario, impacts),
    unknownDisruptions: scenario.disruptions
      .map((disruption, index) => ({ disruption, index }))
      .filter(({ disruption }) => classifyDisruptionType(disruption.restriction_type) === "unknown"),
  };
}

function networkGeometry(scenario, rowHeight = 72) {
  const start = epoch(scenario.recovery_window.start_time);
  const end = epoch(scenario.recovery_window.end_time);
  const durationHours = (end - start) / 3_600_000;
  const width = Math.max(900, Math.ceil(durationHours * 110));
  const left = 108;
  const right = 34;
  const top = 62;
  const height = top + Math.max(scenario.airports.length, 1) * rowHeight + 52;
  const x = (value) => left + ((epoch(value) - start) / (end - start)) * (width - left - right);
  const laneY = new Map(scenario.airports.map((airport, index) => [
    airport.airport_id,
    top + index * rowHeight + rowHeight / 2,
  ]));
  return { start, end, width, height, left, right, top, rowHeight, x, laneY };
}

function renderTimeTicks(svg, scenario, geometry, bottomY) {
  const tickMinutes = chooseTimeTickMinutes(
    scenario.recovery_window.start_time,
    scenario.recovery_window.end_time,
  );
  const tickMs = tickMinutes * 60_000;
  const tickTimes = [];
  for (let time = geometry.start; time <= geometry.end; time += tickMs) tickTimes.push(time);
  if (tickTimes.at(-1) !== geometry.end) tickTimes.push(geometry.end);

  for (const time of tickTimes) {
    const x = geometry.x(time);
    svg.append(svgElement("line", {
      x1: x, y1: geometry.top - 26, x2: x, y2: bottomY,
      class: "viz-axis-grid",
    }));
    const label = svgElement("text", {
      x, y: geometry.top - 34, class: "viz-axis-label", "text-anchor": "middle",
    });
    label.textContent = formatUtcTime(time);
    svg.append(label);
  }
}

function addArrowMarkers(svg) {
  const definitions = svgElement("defs");
  const colors = {
    normal: "#173f35",
    direct: "#a73d36",
    downstream: "#c47c17",
    recovered: "#173f35",
    delayed: "#17739a",
    rerouted: "#6654a3",
    reassigned: "#147c73",
    cancelled: "#a73d36",
  };
  for (const [status, color] of Object.entries(colors)) {
    const marker = svgElement("marker", {
      id: `viz-arrow-${status}`,
      markerWidth: 8,
      markerHeight: 8,
      refX: 7,
      refY: 3.5,
      orient: "auto",
      markerUnits: "strokeWidth",
    });
    marker.append(svgElement("path", { d: "M0,0 L0,7 L7,3.5 z", fill: color }));
    definitions.append(marker);
  }
  svg.append(definitions);
}

function selectFlight(flightId) {
  selectedFlightId = flightId;
  renderTimeSpaceNetwork();
  renderFlightDetail();
}

function renderDisruptions(svg, geometry) {
  for (const disruption of currentModel.scenario.disruptions) {
    const y = geometry.laneY.get(disruption.airport);
    if (y === undefined) continue;
    const x1 = geometry.x(disruption.start_time);
    const x2 = geometry.x(disruption.end_time);
    const group = svgElement("g", { class: "viz-disruption" });
    group.append(svgElement("rect", {
      x: x1,
      y: y - geometry.rowHeight / 2 + 5,
      width: Math.max(2, x2 - x1),
      height: geometry.rowHeight - 10,
      rx: 5,
    }));
    const label = svgElement("text", {
      x: x1 + 6,
      y: y + 5,
      class: "viz-disruption-label",
    });
    label.textContent = `${disruption.restriction_type} · ${disruption.capacity_change}`;
    group.append(label);
    const title = svgElement("title");
    title.textContent = `${disruption.airport} · ${formatUtcTime(disruption.start_time)}–${formatUtcTime(disruption.end_time)} UTC\n${disruption.restriction_type} · 容量变化 ${disruption.capacity_change}`;
    group.append(title);
    svg.append(group);
  }
}

function renderFlights(svg, geometry) {
  currentModel.scenario.flights.forEach((flight) => {
    const originY = geometry.laneY.get(flight.origin);
    const destinationY = geometry.laneY.get(flight.destination);
    if (originY === undefined || destinationY === undefined) return;
    const impact = currentModel.impacts.get(flight.flight_id);
    const displayStatus = networkMode === "original" ? "normal" : impact.status;
    const selected = selectedFlightId === flight.flight_id;
    const x1 = geometry.x(flight.sched_dep);
    const x2 = geometry.x(flight.sched_arr);
    const group = svgElement("g", {
      class: `viz-flight viz-flight--${displayStatus}${selected ? " viz-flight--selected" : ""}`,
      role: "button",
      tabindex: "0",
      "aria-label": `${flight.flight_id}，${flight.origin} 至 ${flight.destination}，${statusLabel(displayStatus)}`,
      "data-flight-id": flight.flight_id,
    });
    group.append(svgElement("line", {
      x1, y1: originY, x2, y2: destinationY,
      class: "viz-flight-hit",
    }));
    group.append(svgElement("line", {
      x1, y1: originY, x2, y2: destinationY,
      class: "viz-flight-line",
      "marker-end": `url(#viz-arrow-${displayStatus})`,
    }));
    group.append(svgElement("circle", { cx: x1, cy: originY, r: 4, class: "viz-flight-origin" }));
    const label = svgElement("text", {
      x: (x1 + x2) / 2,
      y: (originY + destinationY) / 2 - 9,
      class: "viz-flight-label",
      "text-anchor": "middle",
    });
    label.textContent = flight.flight_id;
    group.append(label);
    const title = svgElement("title");
    title.textContent = `${flight.flight_id}: ${flight.origin} → ${flight.destination}\n${formatUtcTime(flight.sched_dep)}–${formatUtcTime(flight.sched_arr)} UTC\n${statusLabel(displayStatus)}`;
    group.append(title);
    group.addEventListener("click", () => selectFlight(flight.flight_id));
    group.addEventListener("keydown", (event) => {
      if (event.key === "Enter" || event.key === " ") {
        event.preventDefault();
        selectFlight(flight.flight_id);
      }
    });
    svg.append(group);
  });
}

function bindFlightSelection(group, flightId) {
  group.addEventListener("click", () => selectFlight(flightId));
  group.addEventListener("keydown", (event) => {
    if (event.key === "Enter" || event.key === " ") {
      event.preventDefault();
      selectFlight(flightId);
    }
  });
}

function renderRecoveredFlights(svg, geometry) {
  for (const view of currentModel.recoveredFlights) {
    const { flight, resolved } = view;
    if (!resolved) continue;
    const originalOriginY = geometry.laneY.get(flight.origin);
    const originalDestinationY = geometry.laneY.get(flight.destination);
    if (originalOriginY === undefined || originalDestinationY === undefined) continue;
    const originalX1 = geometry.x(flight.sched_dep);
    const originalX2 = geometry.x(flight.sched_arr);
    const selected = selectedFlightId === flight.flight_id;
    const group = svgElement("g", {
      class: `viz-flight viz-flight--${view.visualStatus}${selected ? " viz-flight--selected" : ""}`,
      role: "button",
      tabindex: "0",
      "aria-label": `${flight.flight_id}，${recoveredStatusLabel(view)}`,
      "data-flight-id": flight.flight_id,
    });

    if (view.changed) {
      group.append(svgElement("line", {
        x1: originalX1,
        y1: originalOriginY,
        x2: originalX2,
        y2: originalDestinationY,
        class: "viz-flight-ghost",
      }));
    }

    if (view.cancelled) {
      group.append(svgElement("line", {
        x1: originalX1,
        y1: originalOriginY,
        x2: originalX2,
        y2: originalDestinationY,
        class: "viz-flight-hit",
      }));
      group.append(svgElement("line", {
        x1: originalX1,
        y1: originalOriginY,
        x2: originalX2,
        y2: originalDestinationY,
        class: "viz-flight-line",
      }));
      const middleX = (originalX1 + originalX2) / 2;
      const middleY = (originalOriginY + originalDestinationY) / 2;
      group.append(
        svgElement("line", {
          x1: middleX - 6, y1: middleY - 6, x2: middleX + 6, y2: middleY + 6,
          class: "viz-cancel-mark",
        }),
        svgElement("line", {
          x1: middleX - 6, y1: middleY + 6, x2: middleX + 6, y2: middleY - 6,
          class: "viz-cancel-mark",
        }),
      );
      const label = svgElement("text", {
        x: middleX, y: middleY - 12, class: "viz-flight-label", "text-anchor": "middle",
      });
      label.textContent = `${flight.flight_id} · 取消`;
      group.append(label);
    } else {
      const originY = geometry.laneY.get(resolved.recovered_origin);
      const destinationY = geometry.laneY.get(resolved.recovered_destination);
      if (originY === undefined || destinationY === undefined) continue;
      const x1 = geometry.x(resolved.recovered_dep);
      const x2 = geometry.x(resolved.recovered_arr);
      group.append(svgElement("line", {
        x1, y1: originY, x2, y2: destinationY, class: "viz-flight-hit",
      }));
      group.append(svgElement("line", {
        x1, y1: originY, x2, y2: destinationY,
        class: "viz-flight-line",
        "marker-end": `url(#viz-arrow-${view.visualStatus})`,
      }));
      group.append(svgElement("circle", {
        cx: x1, cy: originY, r: 4, class: "viz-flight-origin",
      }));
      const label = svgElement("text", {
        x: (x1 + x2) / 2,
        y: (originY + destinationY) / 2 - 9,
        class: "viz-flight-label",
        "text-anchor": "middle",
      });
      const delay = resolved.departure_delay_minutes || 0;
      label.textContent = delay > 0 ? `${flight.flight_id} · +${delay}m` : flight.flight_id;
      group.append(label);
      const resourceChanges = [
        view.aircraftReassigned ? "飞机改派" : null,
        view.crewReassigned ? "机组改派" : null,
      ].filter(Boolean);
      if (resourceChanges.length) {
        const resourceLabel = svgElement("text", {
          x: (x1 + x2) / 2,
          y: (originY + destinationY) / 2 + 13,
          class: "viz-resource-marker",
          "text-anchor": "middle",
        });
        resourceLabel.textContent = resourceChanges.join(" / ");
        group.append(resourceLabel);
      }
    }

    const title = svgElement("title");
    if (view.cancelled) {
      title.textContent = `${flight.flight_id} · 已取消\n原计划：${flight.origin} → ${flight.destination}\n${formatUtcTime(flight.sched_dep)}–${formatUtcTime(flight.sched_arr)} UTC`;
    } else {
      const resources = [
        `飞机：${flight.original_aircraft} → ${resolved.aircraft_id}`,
        `机组：${flight.original_crew} → ${resolved.crew_id}`,
      ].join("\n");
      title.textContent = `${flight.flight_id} · ${recoveredStatusLabel(view)}\n恢复航线：${resolved.recovered_origin} → ${resolved.recovered_destination}\n${formatUtcTime(resolved.recovered_dep)}–${formatUtcTime(resolved.recovered_arr)} UTC\n${resources}`;
    }
    group.append(title);
    bindFlightSelection(group, flight.flight_id);
    svg.append(group);
  }
}

function renderTimeSpaceNetwork() {
  const container = document.querySelector("#time-space-network");
  container.replaceChildren();
  if (!currentModel) return;
  const { scenario } = currentModel;
  const geometry = networkGeometry(scenario);
  const svg = svgElement("svg", {
    class: "viz-network-svg",
    viewBox: `0 0 ${geometry.width} ${geometry.height}`,
    width: geometry.width,
    height: geometry.height,
    role: "img",
    "aria-label": "航班时空网络",
  });
  addArrowMarkers(svg);
  const bottomY = geometry.top + Math.max(scenario.airports.length, 1) * geometry.rowHeight;
  renderTimeTicks(svg, scenario, geometry, bottomY);

  for (const airport of scenario.airports) {
    const y = geometry.laneY.get(airport.airport_id);
    svg.append(svgElement("line", {
      x1: geometry.left, y1: y, x2: geometry.width - geometry.right, y2: y,
      class: "viz-airport-lane",
    }));
    const label = svgElement("text", {
      x: geometry.left - 18, y: y + 5, class: "viz-airport-label", "text-anchor": "end",
    });
    label.textContent = airport.airport_id;
    svg.append(label);
  }

  if (networkMode === "disruption") renderDisruptions(svg, geometry);
  if (networkMode === "recovered") renderRecoveredFlights(svg, geometry);
  else renderFlights(svg, geometry);
  if (!scenario.flights.length) {
    const empty = svgElement("text", {
      x: geometry.width / 2, y: geometry.height / 2, class: "viz-empty-svg", "text-anchor": "middle",
    });
    empty.textContent = "此 Scenario 中没有计划航班。";
    svg.append(empty);
  }
  container.append(svg);
}

function renderModeButton(label, mode, disabled = false) {
  const button = document.createElement("button");
  button.className = "viz-mode-button";
  button.textContent = label;
  button.disabled = disabled;
  button.setAttribute("aria-pressed", String(networkMode === mode));
  if (disabled) {
    button.title = "完成优化求解后可用";
    const suffix = document.createElement("span");
    suffix.textContent = "完成优化求解后可用";
    button.append(suffix);
  } else {
    button.addEventListener("click", () => {
      networkMode = mode;
      renderVisualizationToolbar();
      renderTimeSpaceNetwork();
      renderFlightDetail();
    });
  }
  return button;
}

function legendItem(className, label) {
  const item = document.createElement("span");
  item.className = "viz-legend-item";
  const swatch = document.createElement("span");
  swatch.className = `viz-legend-swatch ${className}`;
  item.append(swatch, document.createTextNode(label));
  return item;
}

function renderVisualizationToolbar() {
  const toolbar = document.querySelector("#viz-toolbar");
  toolbar.replaceChildren();
  const modes = document.createElement("div");
  modes.className = "viz-mode-group";
  modes.append(
    renderModeButton("原始计划", "original"),
    renderModeButton("扰动叠加", "disruption"),
    renderModeButton("恢复计划", "recovered", !currentModel.recoveredAvailable),
  );

  const legend = document.createElement("div");
  legend.className = "viz-legend";
  legend.append(legendItem("is-normal", "正常 · 实线"));
  if (networkMode === "disruption") {
    legend.append(
      legendItem("is-direct", "直接暴露 · 粗实线"),
      legendItem("is-downstream", "下游风险 · 虚线"),
      legendItem("is-disruption", "已知扰动时间窗"),
    );
  } else if (networkMode === "recovered") {
    legend.replaceChildren(
      legendItem("is-recovered", "按原计划执行"),
      legendItem("is-delayed", "延误"),
      legendItem("is-rerouted", "O-D 变更"),
      legendItem("is-reassigned", "飞机 / 机组改派"),
      legendItem("is-cancelled", "取消"),
      legendItem("is-ghost", "原计划位置"),
    );
  }

  const summary = document.createElement("div");
  summary.className = "viz-impact-summary";
  const counts = { direct: 0, downstream: 0, normal: 0 };
  for (const impact of currentModel.impacts.values()) counts[impact.status] += 1;
  if (networkMode === "original") {
    summary.textContent = `${currentModel.scenario.flights.length} 个计划航班`;
  } else if (networkMode === "recovered") {
    const changed = currentModel.recoveredFlights.filter((item) => item.changed).length;
    const delayed = currentModel.recoveredFlights.filter((item) => item.delayed).length;
    const rerouted = currentModel.recoveredFlights.filter((item) => item.odChanged).length;
    const reassigned = currentModel.recoveredFlights.filter(
      (item) => item.aircraftReassigned || item.crewReassigned,
    ).length;
    const cancelled = currentModel.recoveredFlights.filter((item) => item.cancelled).length;
    summary.textContent = `变更 ${changed} · 延误 ${delayed} · O-D 变更 ${rerouted} · 资源改派 ${reassigned} · 取消 ${cancelled}`;
  } else {
    summary.textContent = `直接暴露 ${counts.direct} · 下游风险 ${counts.downstream} · 正常 ${counts.normal}`;
  }

  toolbar.append(modes, legend, summary);
  if (networkMode === "disruption" && !currentModel.scenario.disruptions.length) {
    toolbar.append(textElement("p", "未定义扰动事件。所有航班均保持正常状态。", "viz-notice"));
  }
  if (networkMode === "disruption" && currentModel.unknownDisruptions.length) {
    const types = currentModel.unknownDisruptions
      .map(({ disruption }) => disruption.restriction_type)
      .join(", ");
    toolbar.append(textElement(
      "p",
      `未知的限制类型：${types}。系统会显示该扰动，但不会据此推断航班暴露。`,
      "viz-notice viz-notice--warning",
    ));
  }
}

function definitionList(entries) {
  const list = document.createElement("dl");
  list.className = "viz-definition-list";
  for (const [label, value] of entries) {
    list.append(textElement("dt", label), textElement("dd", String(value)));
  }
  return list;
}

function sequenceClass(flightId) {
  if (flightId === selectedFlightId) return "is-selected";
  if (networkMode === "original") return "is-normal";
  if (networkMode === "recovered") {
    return `is-${currentModel.recoveredByFlightId.get(flightId)?.visualStatus || "normal"}`;
  }
  const status = currentModel.impacts.get(flightId)?.status || "normal";
  return `is-${status}`;
}

function renderSequence(flightIds) {
  const sequence = document.createElement("div");
  sequence.className = "viz-sequence";
  flightIds.forEach((flightId, index) => {
    if (index) sequence.append(textElement("span", "→", "viz-sequence-arrow"));
    const button = document.createElement("button");
    button.className = `viz-flight-chip ${sequenceClass(flightId)}`;
    button.textContent = flightId;
    button.disabled = !currentModel.indexes.flightsById.has(flightId);
    button.addEventListener("click", () => selectFlight(flightId));
    sequence.append(button);
  });
  return sequence;
}

function detailSection(title) {
  const section = document.createElement("section");
  section.className = "viz-detail-section";
  section.append(textElement("h3", title));
  return section;
}

function renderImpactExplanation(section, impact) {
  if (networkMode === "original") {
    section.append(textElement(
      "p",
      "原始计划模式有意隐藏影响状态。",
      "viz-detail-note",
    ));
    return;
  }
  const badge = textElement("span", statusLabel(impact.status), `viz-status-badge is-${impact.status}`);
  section.append(badge);
  if (impact.status === "direct") {
    const list = document.createElement("ul");
    list.className = "viz-reason-list";
    for (const reason of impact.directDisruptions) {
      const item = document.createElement("li");
      const movement = reason.type === "departure" ? "起飞" : reason.type === "arrival" ? "到达" : "起飞与到达";
      item.textContent = `${reason.airport} ${movement}扰动 · ${formatUtcTime(reason.startTime)}–${formatUtcTime(reason.endTime)} UTC · ${reason.restrictionType} · 容量变化 ${reason.capacityChange}`;
      list.append(item);
    }
    section.append(list);
  } else if (impact.status === "downstream") {
    const list = document.createElement("ul");
    list.className = "viz-reason-list";
    for (const source of impact.propagationSources) {
      const resource = source.type === "aircraft" ? "飞机" : "机组";
      const item = document.createElement("li");
      item.textContent = `${resource} ${source.resourceId}，位于 ${source.sourceFlightId} 的下游`;
      list.append(item);
    }
    section.append(list);
  } else {
    section.append(textElement(
      "p",
      "按当前确定性规则，未发现直接暴露，也未发现由飞机或机组关联导致的下游风险。",
      "viz-detail-note",
    ));
  }
}

function changeBadge(text, className) {
  return textElement("span", text, `viz-change-badge ${className}`);
}

function renderRecoveryExplanation(section, view) {
  if (!view?.resolved) {
    section.append(textElement("p", "当前航班缺少可用的恢复结果。", "viz-detail-note"));
    return;
  }
  const badges = document.createElement("div");
  badges.className = "viz-change-list";
  if (!view.changed) badges.append(changeBadge("按原计划执行", "is-recovered"));
  if (view.cancelled) badges.append(changeBadge("已取消", "is-cancelled"));
  if (view.delayed) badges.append(changeBadge(
    `起飞延误 +${view.resolved.departure_delay_minutes || 0} 分钟`,
    "is-delayed",
  ));
  if (view.odChanged) badges.append(changeBadge("O-D 变更", "is-rerouted"));
  if (view.aircraftReassigned) badges.append(changeBadge("飞机改派", "is-reassigned"));
  if (view.crewReassigned) badges.append(changeBadge("机组改派", "is-reassigned"));
  section.append(badges);
  section.append(textElement(
    "p",
    view.cancelled
      ? "该航班未执行；图中的灰色虚线保留其原计划位置用于审计对照。"
      : view.changed
        ? "彩色实线表示恢复方案；灰色虚线表示该航班的原计划位置。"
        : "恢复方案未改变该航班的航线、时刻、飞机或机组。",
    "viz-detail-note",
  ));
}

function renderAircraftDetail(parent, flight, recoveryView = null) {
  const section = detailSection("飞机");
  const aircraft = currentModel.indexes.aircraftById.get(flight.original_aircraft);
  if (!aircraft) {
    section.append(textElement("p", "没有关联的飞机数据。", "viz-detail-note"));
  } else {
    section.append(definitionList([
      ["机尾号", aircraft.tail_id],
      ["机型", aircraft.equipment_type],
      ["初始机场", aircraft.initial_station_at_t],
      ["期末要求机场", aircraft.required_station_at_T_end],
      ["需要维修", aircraft.maintenance_required ? "是" : "否"],
    ]));
    section.append(textElement("p", "原始轮转", "viz-sequence-label"));
    section.append(renderSequence(aircraft.original_rotation));
  }
  if (networkMode === "recovered" && recoveryView?.resolved && !recoveryView.cancelled) {
    const outcome = currentModel.recoveredResult?.aircraft_outcomes?.find(
      (item) => item.aircraft_id === recoveryView.resolved.aircraft_id,
    );
    section.append(definitionList([
      ["恢复方案飞机", recoveryView.resolved.aircraft_id],
      ["飞机改派", recoveryView.aircraftReassigned ? "是" : "否"],
    ]));
    if (outcome) {
      section.append(textElement("p", "恢复轮转", "viz-sequence-label"));
      section.append(renderSequence(outcome.recovered_flight_ids));
    }
  }
  parent.append(section);
}

function renderCrewDetail(parent, flight, recoveryView = null) {
  const section = detailSection("机组");
  const crew = currentModel.indexes.crewById.get(flight.original_crew);
  if (!crew) {
    section.append(textElement("p", "没有关联的机组数据。", "viz-detail-note"));
  } else {
    section.append(definitionList([
      ["机组 ID", crew.crew_id],
      ["资质等级", crew.rating],
      ["初始机场", crew.start_station_at_t],
      ["期末要求机场", crew.required_station_at_T_end],
    ]));
    section.append(textElement("p", "原始配对", "viz-sequence-label"));
    section.append(renderSequence(crew.original_pairing));
    crew.original_duties.forEach((duty, index) => {
      section.append(textElement("p", `执勤任务 ${index + 1}`, "viz-sequence-label"));
      section.append(renderSequence(duty));
    });
    section.append(textElement("p", "此确定性可视化不计算机组执勤合法性。", "viz-detail-footnote"));
  }
  if (networkMode === "recovered" && recoveryView?.resolved && !recoveryView.cancelled) {
    const outcome = currentModel.recoveredResult?.crew_outcomes?.find(
      (item) => item.crew_id === recoveryView.resolved.crew_id,
    );
    section.append(definitionList([
      ["恢复方案机组", recoveryView.resolved.crew_id],
      ["机组改派", recoveryView.crewReassigned ? "是" : "否"],
    ]));
    if (outcome) {
      section.append(textElement("p", "恢复配对（OPERATE）", "viz-sequence-label"));
      section.append(renderSequence(outcome.operated_flights));
    }
  }
  parent.append(section);
}

function renderPassengerDetail(parent, flight) {
  const section = detailSection("旅客流（Passenger Commodities）");
  const passengers = currentModel.scenario.passengers.filter(
    (passenger) => passenger.original_itinerary.includes(flight.flight_id),
  );
  if (!passengers.length) {
    section.append(textElement("p", "没有旅客流使用此航班。", "viz-detail-note"));
    parent.append(section);
    return;
  }
  const total = passengers.reduce((sum, passenger) => sum + passenger.count, 0);
  section.append(textElement("p", `${passengers.length} 个旅客组 · 共 ${total} 名旅客`, "viz-passenger-summary"));
  for (const passenger of passengers) {
    const card = document.createElement("article");
    card.className = "viz-passenger-card";
    card.append(textElement("strong", `${passenger.pax_group_id} · ${passenger.count} 名旅客`));
    card.append(textElement("span", `${passenger.origin} → ${passenger.destination}`));
    card.append(renderSequence(passenger.original_itinerary));
    if (networkMode === "disruption") {
      const risk = currentModel.passengerRisk.get(passenger.pax_group_id);
      card.append(textElement(
        "span",
        risk.atRisk
          ? `存在风险 · 首个受影响航班 ${risk.firstAffectedFlightId}`
          : "当前未标记风险",
        `viz-passenger-risk ${risk.atRisk ? "is-risk" : "is-clear"}`,
      ));
    }
    section.append(card);
  }
  section.append(textElement(
    "p",
    "“存在风险”仅表示行程中包含被运行规则标记的航班，并不等同于已经延误、错失衔接或完成改签。",
    "viz-detail-footnote",
  ));
  parent.append(section);
}

function renderFlightDetail() {
  const detail = document.querySelector("#flight-detail");
  detail.replaceChildren();
  detail.append(textElement("p", "所选航班", "section-kicker"));
  if (!selectedFlightId) {
    detail.append(textElement("h2", "资源关联"));
    detail.append(textElement(
      "p",
      "请在网络图中选择一个航班，以查看其飞机、机组和旅客关联。",
      "viz-detail-empty",
    ));
    return;
  }
  const flight = currentModel.indexes.flightsById.get(selectedFlightId);
  if (!flight) {
    selectedFlightId = null;
    renderFlightDetail();
    return;
  }
  const recoveryView = currentModel.recoveredByFlightId.get(flight.flight_id);
  const titleRoute = networkMode === "recovered" && recoveryView?.resolved && !recoveryView.cancelled
    ? `${recoveryView.resolved.recovered_origin} → ${recoveryView.resolved.recovered_destination}`
    : `${flight.origin} → ${flight.destination}`;
  detail.append(textElement(
    "h2",
    `${flight.flight_id} · ${recoveryView?.cancelled && networkMode === "recovered" ? "已取消" : titleRoute}`,
  ));
  const summary = detailSection("航班摘要");
  const summaryRows = [
    ["计划起飞", formatUtcDateTime(flight.sched_dep)],
    ["计划到达", formatUtcDateTime(flight.sched_arr)],
    ["航程时长", `${flight.duration} 分钟`],
    ["机型", flight.original_equipment],
    ["战略航班", flight.strategic_flag ? "是" : "否"],
    ["市场航班", flight.market_flag ? "是" : "否"],
    ["最大允许恢复延误", `${flight.max_delay} 分钟`],
  ];
  if (networkMode === "recovered" && recoveryView?.resolved) {
    summaryRows.push(
      ["所选 Flight Option", recoveryView.resolved.selected_option_id],
      ["恢复状态", recoveryView.cancelled ? "取消" : "执飞"],
      ["恢复起飞", recoveryView.cancelled ? "—" : formatUtcDateTime(recoveryView.resolved.recovered_dep)],
      ["恢复到达", recoveryView.cancelled ? "—" : formatUtcDateTime(recoveryView.resolved.recovered_arr)],
      ["起飞 / 到达延误", recoveryView.cancelled
        ? "—"
        : `${recoveryView.resolved.departure_delay_minutes} / ${recoveryView.resolved.arrival_delay_minutes} 分钟`],
    );
  }
  summary.append(definitionList(summaryRows));
  detail.append(summary);

  const impactSection = detailSection(networkMode === "recovered" ? "恢复变更" : "影响说明");
  if (networkMode === "recovered") renderRecoveryExplanation(impactSection, recoveryView);
  else renderImpactExplanation(impactSection, currentModel.impacts.get(flight.flight_id));
  detail.append(impactSection);
  renderAircraftDetail(detail, flight, recoveryView);
  renderCrewDetail(detail, flight, recoveryView);
  renderPassengerDetail(detail, flight);
}

function capacityStatusLabel(status) {
  return {
    empty: "无计划流量",
    within: "未达到容量上限",
    at: "达到容量上限",
    over: "超过容量上限",
    zero: "容量为零且无计划流量",
  }[status];
}

function renderCapacityHeatmap() {
  const container = document.querySelector("#capacity-heatmap");
  container.replaceChildren();
  const controls = document.createElement("div");
  controls.className = "viz-capacity-controls";
  for (const [mode, label] of [["departures", "起飞"], ["arrivals", "到达"]]) {
    const button = document.createElement("button");
    button.className = "viz-mode-button";
    button.textContent = label;
    button.setAttribute("aria-pressed", String(capacityMode === mode));
    button.addEventListener("click", () => {
      capacityMode = mode;
      renderCapacityHeatmap();
    });
    controls.append(button);
  }
  controls.append(textElement(
    "p",
    "直接使用输入的 AirportInterval 数值；不反推扰动前容量，也不重建机位利用率。",
    "viz-capacity-note",
  ));
  container.append(controls);

  if (!currentModel.scenario.airport_intervals.length) {
    container.append(textElement("p", "未定义机场容量时间区间。", "viz-empty-state"));
    return;
  }

  const scenario = currentModel.scenario;
  const geometry = networkGeometry(scenario, 62);
  const cells = deriveCapacityCells(scenario, capacityMode);
  const svg = svgElement("svg", {
    class: "viz-capacity-svg",
    viewBox: `0 0 ${geometry.width} ${geometry.height}`,
    width: geometry.width,
    height: geometry.height,
    role: "img",
    "aria-label": `机场${capacityMode === "departures" ? "起飞" : "到达"}容量热力图`,
  });
  const bottomY = geometry.top + Math.max(scenario.airports.length, 1) * geometry.rowHeight;
  renderTimeTicks(svg, scenario, geometry, bottomY);
  for (const airport of scenario.airports) {
    const y = geometry.laneY.get(airport.airport_id);
    svg.append(svgElement("line", {
      x1: geometry.left, y1: y, x2: geometry.width - geometry.right, y2: y,
      class: "viz-airport-lane",
    }));
    const label = svgElement("text", {
      x: geometry.left - 18, y: y + 5, class: "viz-airport-label", "text-anchor": "end",
    });
    label.textContent = airport.airport_id;
    svg.append(label);
  }
  for (const cell of cells) {
    const y = geometry.laneY.get(cell.airport);
    if (y === undefined) continue;
    const x1 = geometry.x(cell.startTime);
    const x2 = geometry.x(cell.endTime);
    const group = svgElement("g", {
      class: `viz-capacity-cell viz-capacity-cell--${cell.status}`,
      tabindex: "0",
      role: "img",
      "aria-label": `${cell.airport}，${formatUtcTime(cell.startTime)} 至 ${formatUtcTime(cell.endTime)} UTC，负荷 ${cell.load} / 容量 ${cell.capacity}，${capacityStatusLabel(cell.status)}`,
    });
    group.append(svgElement("rect", {
      x: x1, y: y - 21, width: Math.max(8, x2 - x1), height: 42, rx: 6,
    }));
    const label = svgElement("text", {
      x: (x1 + x2) / 2, y: y + 5, "text-anchor": "middle",
    });
    label.textContent = `${cell.load} / ${cell.capacity}`;
    group.append(label);
    const title = svgElement("title");
    const weather = cell.weatherRestrictions.length ? cell.weatherRestrictions.join(", ") : "无";
    const movement = capacityMode === "departures" ? "计划起飞" : "计划到达";
    title.textContent = `${cell.airport} · ${formatUtcTime(cell.startTime)}–${formatUtcTime(cell.endTime)} UTC\n${movement}：${cell.load}\n容量：${cell.capacity}\n${capacityStatusLabel(cell.status)}\n机位容量：${cell.gateCapacity}\n计划机位占用：此可视化未计算\n宵禁：${cell.curfew ? "是" : "否"}\n天气限制：${weather}`;
    group.append(title);
    svg.append(group);
  }
  container.append(svg);

  const legend = document.createElement("div");
  legend.className = "viz-capacity-legend";
  for (const [status, label] of [
    ["empty", "无计划流量"],
    ["within", "未达到容量上限"],
    ["at", "达到容量上限"],
    ["over", "超过容量上限 / 阻塞"],
    ["zero", "容量为零且无计划流量"],
  ]) {
    legend.append(legendItem(`capacity-${status}`, label));
  }
  container.append(legend);
}

export function renderVisualization(scenario, recoveredResult = null) {
  currentModel = deriveVisualizationModel(scenario, recoveredResult);
  if (networkMode === "recovered" && !currentModel.recoveredAvailable) {
    networkMode = "disruption";
  }
  if (selectedFlightId && !currentModel.indexes.flightsById.has(selectedFlightId)) {
    selectedFlightId = null;
  }
  renderVisualizationToolbar();
  renderTimeSpaceNetwork();
  renderFlightDetail();
  renderCapacityHeatmap();
}

export function renderVisualizationLoading() {
  currentModel = null;
  document.querySelector("#viz-toolbar").replaceChildren(
    textElement("p", "正在校验当前 Scenario…", "viz-loading"),
  );
  document.querySelector("#time-space-network").replaceChildren();
  document.querySelector("#flight-detail").replaceChildren();
  document.querySelector("#capacity-heatmap").replaceChildren();
}

export function renderVisualizationBlocked(result, onBack) {
  currentModel = null;
  const panel = document.createElement("section");
  panel.className = "viz-blocked";
  panel.append(textElement("p", "需要通过数据校验", "section-kicker"));
  panel.append(textElement("h2", "可视化已阻止"));
  panel.append(textElement(
    "p",
    "当前 Scenario 无效，因此系统不会绘制不完整或可能产生误导的图形。",
  ));
  const list = document.createElement("ol");
  for (const error of result.errors) {
    const item = document.createElement("li");
    item.append(textElement("strong", error.location), document.createTextNode(` ${error.message}`));
    list.append(item);
  }
  panel.append(list);
  const back = document.createElement("button");
  back.className = "button primary";
  back.textContent = "返回数据编辑器";
  back.addEventListener("click", onBack);
  panel.append(back);
  document.querySelector("#viz-toolbar").replaceChildren(panel);
  document.querySelector("#time-space-network").replaceChildren(
    textElement("p", "存在校验错误时不绘制图形。", "viz-empty-state"),
  );
  document.querySelector("#flight-detail").replaceChildren();
  document.querySelector("#capacity-heatmap").replaceChildren();
}
