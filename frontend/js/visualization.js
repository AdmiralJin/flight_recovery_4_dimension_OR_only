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
    direct: "Directly exposed",
    downstream: "Downstream propagation risk",
    normal: "Normal under current rules",
  }[status];
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

export function deriveVisualizationModel(scenario) {
  const impacts = deriveFlightImpacts(scenario);
  return {
    scenario,
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
  const colors = { normal: "#173f35", direct: "#a73d36", downstream: "#c47c17" };
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
    title.textContent = `${disruption.airport} · ${formatUtcTime(disruption.start_time)}–${formatUtcTime(disruption.end_time)} UTC\n${disruption.restriction_type} · capacity change ${disruption.capacity_change}`;
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
      "aria-label": `${flight.flight_id}, ${flight.origin} to ${flight.destination}, ${statusLabel(displayStatus)}`,
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
    "aria-label": "Flight time-space network",
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
  renderFlights(svg, geometry);
  if (!scenario.flights.length) {
    const empty = svgElement("text", {
      x: geometry.width / 2, y: geometry.height / 2, class: "viz-empty-svg", "text-anchor": "middle",
    });
    empty.textContent = "No scheduled flights in this scenario.";
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
    button.title = "Available after optimization";
    const suffix = document.createElement("span");
    suffix.textContent = "Available after optimization";
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
    renderModeButton("Original Plan", "original"),
    renderModeButton("Disruption Overlay", "disruption"),
    renderModeButton("Recovered Plan", "recovered", true),
  );

  const legend = document.createElement("div");
  legend.className = "viz-legend";
  legend.append(legendItem("is-normal", "Normal · solid"));
  if (networkMode === "disruption") {
    legend.append(
      legendItem("is-direct", "Direct exposure · heavy solid"),
      legendItem("is-downstream", "Downstream risk · dashed"),
      legendItem("is-disruption", "Known disruption window"),
    );
  }

  const summary = document.createElement("div");
  summary.className = "viz-impact-summary";
  const counts = { direct: 0, downstream: 0, normal: 0 };
  for (const impact of currentModel.impacts.values()) counts[impact.status] += 1;
  summary.textContent = networkMode === "original"
    ? `${currentModel.scenario.flights.length} scheduled flights`
    : `${counts.direct} direct · ${counts.downstream} downstream · ${counts.normal} normal`;

  toolbar.append(modes, legend, summary);
  if (networkMode === "disruption" && !currentModel.scenario.disruptions.length) {
    toolbar.append(textElement("p", "No disruptions defined. All flights remain normal.", "viz-notice"));
  }
  if (networkMode === "disruption" && currentModel.unknownDisruptions.length) {
    const types = currentModel.unknownDisruptions
      .map(({ disruption }) => disruption.restriction_type)
      .join(", ");
    toolbar.append(textElement(
      "p",
      `Unknown restriction type: ${types}. Disruption shown, but flight exposure is not inferred.`,
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
      "Impact status is intentionally hidden in Original Plan mode.",
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
      item.textContent = `${reason.airport} ${reason.type} disruption · ${formatUtcTime(reason.startTime)}–${formatUtcTime(reason.endTime)} UTC · ${reason.restrictionType} · capacity change ${reason.capacityChange}`;
      list.append(item);
    }
    section.append(list);
  } else if (impact.status === "downstream") {
    const list = document.createElement("ul");
    list.className = "viz-reason-list";
    for (const source of impact.propagationSources) {
      const resource = source.type === "aircraft" ? "Aircraft" : "Crew";
      const item = document.createElement("li");
      item.textContent = `${resource} ${source.resourceId}, downstream of ${source.sourceFlightId}`;
      list.append(item);
    }
    section.append(list);
  } else {
    section.append(textElement(
      "p",
      "No direct exposure or aircraft/crew downstream risk under the current deterministic rules.",
      "viz-detail-note",
    ));
  }
}

function renderAircraftDetail(parent, flight) {
  const section = detailSection("Aircraft");
  const aircraft = currentModel.indexes.aircraftById.get(flight.original_aircraft);
  if (!aircraft) {
    section.append(textElement("p", "No linked aircraft data.", "viz-detail-note"));
  } else {
    section.append(definitionList([
      ["Tail", aircraft.tail_id],
      ["Equipment", aircraft.equipment_type],
      ["Initial station", aircraft.initial_station_at_t],
      ["Required end station", aircraft.required_station_at_T_end],
      ["Maintenance required", aircraft.maintenance_required],
    ]));
    section.append(textElement("p", "Original rotation", "viz-sequence-label"));
    section.append(renderSequence(aircraft.original_rotation));
  }
  parent.append(section);
}

function renderCrewDetail(parent, flight) {
  const section = detailSection("Crew");
  const crew = currentModel.indexes.crewById.get(flight.original_crew);
  if (!crew) {
    section.append(textElement("p", "No linked crew data.", "viz-detail-note"));
  } else {
    section.append(definitionList([
      ["Crew ID", crew.crew_id],
      ["Rating", crew.rating],
      ["Start station", crew.start_station_at_t],
      ["Required end station", crew.required_station_at_T_end],
    ]));
    section.append(textElement("p", "Original pairing", "viz-sequence-label"));
    section.append(renderSequence(crew.original_pairing));
    crew.original_duties.forEach((duty, index) => {
      section.append(textElement("p", `Duty ${index + 1}`, "viz-sequence-label"));
      section.append(renderSequence(duty));
    });
    section.append(textElement("p", "Duty legality is not computed by this deterministic visualization.", "viz-detail-footnote"));
  }
  parent.append(section);
}

function renderPassengerDetail(parent, flight) {
  const section = detailSection("Passenger commodities");
  const passengers = currentModel.scenario.passengers.filter(
    (passenger) => passenger.original_itinerary.includes(flight.flight_id),
  );
  if (!passengers.length) {
    section.append(textElement("p", "No passenger commodities use this flight.", "viz-detail-note"));
    parent.append(section);
    return;
  }
  const total = passengers.reduce((sum, passenger) => sum + passenger.count, 0);
  section.append(textElement("p", `${passengers.length} group(s) · ${total} passengers represented`, "viz-passenger-summary"));
  for (const passenger of passengers) {
    const card = document.createElement("article");
    card.className = "viz-passenger-card";
    card.append(textElement("strong", `${passenger.pax_group_id} · ${passenger.count} pax`));
    card.append(textElement("span", `${passenger.origin} → ${passenger.destination}`));
    card.append(renderSequence(passenger.original_itinerary));
    if (networkMode === "disruption") {
      const risk = currentModel.passengerRisk.get(passenger.pax_group_id);
      card.append(textElement(
        "span",
        risk.atRisk
          ? `At risk · first affected flight ${risk.firstAffectedFlightId}`
          : "Not currently flagged",
        `viz-passenger-risk ${risk.atRisk ? "is-risk" : "is-clear"}`,
      ));
    }
    section.append(card);
  }
  section.append(textElement(
    "p",
    "At risk means the itinerary contains an operationally flagged flight; it does not mean delayed, misconnected or rebooked.",
    "viz-detail-footnote",
  ));
  parent.append(section);
}

function renderFlightDetail() {
  const detail = document.querySelector("#flight-detail");
  detail.replaceChildren();
  detail.append(textElement("p", "SELECTED FLIGHT", "section-kicker"));
  if (!selectedFlightId) {
    detail.append(textElement("h2", "Resource links"));
    detail.append(textElement(
      "p",
      "Select a flight in the network to inspect aircraft, crew and passenger links.",
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
  detail.append(textElement("h2", `${flight.flight_id} · ${flight.origin} → ${flight.destination}`));
  const summary = detailSection("Flight summary");
  summary.append(definitionList([
    ["Scheduled departure", formatUtcDateTime(flight.sched_dep)],
    ["Scheduled arrival", formatUtcDateTime(flight.sched_arr)],
    ["Duration", `${flight.duration} min`],
    ["Equipment", flight.original_equipment],
    ["Strategic", flight.strategic_flag],
    ["Market", flight.market_flag],
    ["Maximum allowed recovery delay", `${flight.max_delay} min`],
  ]));
  detail.append(summary);

  const impactSection = detailSection("Impact explanation");
  renderImpactExplanation(impactSection, currentModel.impacts.get(flight.flight_id));
  detail.append(impactSection);
  renderAircraftDetail(detail, flight);
  renderCrewDetail(detail, flight);
  renderPassengerDetail(detail, flight);
}

function capacityStatusLabel(status) {
  return {
    empty: "Empty",
    within: "Within capacity",
    at: "At capacity",
    over: "Over capacity",
    zero: "Zero capacity, no scheduled movement",
  }[status];
}

function renderCapacityHeatmap() {
  const container = document.querySelector("#capacity-heatmap");
  container.replaceChildren();
  const controls = document.createElement("div");
  controls.className = "viz-capacity-controls";
  for (const [mode, label] of [["departures", "Departures"], ["arrivals", "Arrivals"]]) {
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
    "Uses AirportInterval values as provided; pre-disruption capacity and gate utilization are not reconstructed.",
    "viz-capacity-note",
  ));
  container.append(controls);

  if (!currentModel.scenario.airport_intervals.length) {
    container.append(textElement("p", "No airport capacity intervals defined.", "viz-empty-state"));
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
    "aria-label": `Airport capacity heatmap for ${capacityMode}`,
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
      "aria-label": `${cell.airport}, ${formatUtcTime(cell.startTime)} to ${formatUtcTime(cell.endTime)} UTC, ${cell.load} of ${cell.capacity}, ${capacityStatusLabel(cell.status)}`,
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
    const weather = cell.weatherRestrictions.length ? cell.weatherRestrictions.join(", ") : "none";
    title.textContent = `${cell.airport} · ${formatUtcTime(cell.startTime)}–${formatUtcTime(cell.endTime)} UTC\nScheduled ${capacityMode}: ${cell.load}\nCapacity: ${cell.capacity}\n${capacityStatusLabel(cell.status)}\nGate capacity: ${cell.gateCapacity}\nPlanned gate occupancy: not computed by this visualization\nCurfew: ${cell.curfew}\nWeather: ${weather}`;
    group.append(title);
    svg.append(group);
  }
  container.append(svg);

  const legend = document.createElement("div");
  legend.className = "viz-capacity-legend";
  for (const [status, label] of [
    ["empty", "No scheduled movement"],
    ["within", "Within capacity"],
    ["at", "At capacity"],
    ["over", "Over capacity / blocked"],
    ["zero", "Zero capacity and zero movement"],
  ]) {
    legend.append(legendItem(`capacity-${status}`, label));
  }
  container.append(legend);
}

export function renderVisualization(scenario) {
  currentModel = deriveVisualizationModel(scenario);
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
    textElement("p", "Validating the current scenario…", "viz-loading"),
  );
  document.querySelector("#time-space-network").replaceChildren();
  document.querySelector("#flight-detail").replaceChildren();
  document.querySelector("#capacity-heatmap").replaceChildren();
}

export function renderVisualizationBlocked(result, onBack) {
  currentModel = null;
  const panel = document.createElement("section");
  panel.className = "viz-blocked";
  panel.append(textElement("p", "VALIDATION REQUIRED", "section-kicker"));
  panel.append(textElement("h2", "Visualization blocked"));
  panel.append(textElement(
    "p",
    "The current scenario is invalid, so no partial or potentially misleading graph was drawn.",
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
  back.textContent = "Back to Data Editor";
  back.addEventListener("click", onBack);
  panel.append(back);
  document.querySelector("#viz-toolbar").replaceChildren(panel);
  document.querySelector("#time-space-network").replaceChildren(
    textElement("p", "No graph rendered while validation errors exist.", "viz-empty-state"),
  );
  document.querySelector("#flight-detail").replaceChildren();
  document.querySelector("#capacity-heatmap").replaceChildren();
}
