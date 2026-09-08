export const sections = [
  { key: "scenario", label: "Scenario", title: "Recovery window" },
  { key: "airports", label: "Airports", title: "Airport master data" },
  { key: "flights", label: "Flights", title: "Scheduled flight legs" },
  { key: "aircraft", label: "Aircraft", title: "Tail rotations" },
  { key: "crew", label: "Crew", title: "Cockpit crew pairings" },
  { key: "passengers", label: "Passengers", title: "Passenger commodities" },
  { key: "airport_intervals", label: "Airport Capacity", title: "Time-dependent airport capacity" },
  { key: "disruptions", label: "Disruptions", title: "Disruption events" },
];

export const columns = {
  airports: [
    ["airport_id", "Airport ID", "text"], ["name", "Name", "text"],
  ],
  flights: [
    ["flight_id", "Flight", "text"], ["origin", "Origin", "text"], ["destination", "Destination", "text"],
    ["sched_dep", "Scheduled dep", "text"], ["sched_arr", "Scheduled arr", "text"], ["duration", "Duration min", "number"],
    ["original_aircraft", "Aircraft", "text"], ["original_equipment", "Equipment", "text"], ["original_crew", "Crew", "text"],
    ["strategic_flag", "Strategic", "boolean"], ["market_flag", "Market", "boolean"], ["min_seats", "Min seats", "number"], ["max_delay", "Max delay", "number"],
  ],
  aircraft: [
    ["tail_id", "Tail", "text"], ["equipment_type", "Equipment", "text"], ["initial_station_at_t", "Start station", "text"],
    ["required_station_at_T_end", "End station", "text"], ["maintenance_required", "Maintenance", "boolean"],
    ["maintenance_stations", "Maintenance stations", "json"], ["original_rotation", "Original rotation", "json"],
  ],
  crew: [
    ["crew_id", "Crew", "text"], ["rating", "Rating", "text"], ["start_station_at_t", "Start station", "text"],
    ["required_station_at_T_end", "End station", "text"], ["original_duties", "Original duties", "json"], ["original_pairing", "Original pairing", "json"],
  ],
  passengers: [
    ["pax_group_id", "Group", "text"], ["count", "Count", "number"], ["origin", "Origin", "text"], ["destination", "Destination", "text"],
    ["original_departure", "Original departure", "text"], ["scheduled_arrival", "Scheduled arrival", "text"], ["original_itinerary", "Original itinerary", "json"],
  ],
  airport_intervals: [
    ["airport", "Airport", "text"], ["start_time", "Start", "text"], ["end_time", "End", "text"],
    ["arr_capacity", "Arr cap", "number"], ["dep_capacity", "Dep cap", "number"], ["gate_capacity", "Gate cap", "number"],
    ["curfew_flag", "Curfew", "boolean"], ["weather_restrictions", "Weather restrictions", "json"],
  ],
  disruptions: [
    ["airport", "Airport", "text"], ["start_time", "Start", "text"], ["end_time", "End", "text"],
    ["capacity_change", "Capacity change", "number"], ["restriction_type", "Restriction type", "text"],
  ],
};

export function blankRow(section) {
  const row = {};
  for (const [key, , type] of columns[section]) {
    row[key] = type === "boolean" ? false : type === "number" ? 0 : type === "json" ? [] : "";
  }
  return row;
}

export function parseInput(input, type) {
  if (type === "number") return Number(input.value);
  if (type === "boolean") return input.value === "true";
  if (type === "json") return JSON.parse(input.value || "[]");
  return input.value;
}

export function renderEditor(container, section, data, onChange) {
  container.replaceChildren();
  if (section === "scenario") {
    const form = document.createElement("div");
    form.className = "scenario-form";
    const fields = [
      ["scenario_id", "Scenario ID", data.scenario_id],
      ["start_time", "Recovery start", data.recovery_window.start_time],
      ["end_time", "Recovery end", data.recovery_window.end_time],
    ];
    for (const [key, label, value] of fields) {
      const wrapper = document.createElement("div");
      wrapper.className = "field";
      const labelElement = document.createElement("label");
      labelElement.textContent = label;
      const input = document.createElement("input");
      input.type = "text";
      input.value = value;
      input.dataset.field = key;
      input.addEventListener("change", () => {
        if (key === "scenario_id") data.scenario_id = input.value;
        else data.recovery_window[key] = input.value;
        onChange();
      });
      wrapper.append(labelElement, input);
      form.append(wrapper);
    }
    const note = document.createElement("p");
    note.className = "field-note";
    note.textContent = "Use ISO 8601 timestamps. The bundled example uses UTC (Z), so imports and exports remain unambiguous.";
    form.append(note);
    container.append(form);
    return;
  }

  const rows = data[section];
  if (!rows.length) {
    const empty = document.createElement("div");
    empty.className = "empty-state";
    empty.textContent = "No records yet. Choose Add Row to begin.";
    container.append(empty);
    return;
  }

  const table = document.createElement("table");
  const thead = document.createElement("thead");
  const headRow = document.createElement("tr");
  headRow.append(document.createElement("th"));
  for (const [, label] of columns[section]) {
    const th = document.createElement("th");
    th.textContent = label;
    headRow.append(th);
  }
  thead.append(headRow);
  const tbody = document.createElement("tbody");

  rows.forEach((row, rowIndex) => {
    const tr = document.createElement("tr");
    const selectorCell = document.createElement("td");
    selectorCell.className = "selector";
    const selector = document.createElement("input");
    selector.type = "radio";
    selector.name = "selected-row";
    selector.value = String(rowIndex);
    selector.setAttribute("aria-label", `Select row ${rowIndex + 1}`);
    selectorCell.append(selector);
    tr.append(selectorCell);

    for (const [key, , type] of columns[section]) {
      const td = document.createElement("td");
      let input;
      if (type === "boolean") {
        input = document.createElement("select");
        input.className = "boolean-select";
        for (const value of [false, true]) {
          const option = document.createElement("option");
          option.value = String(value);
          option.textContent = String(value);
          option.selected = row[key] === value;
          input.append(option);
        }
      } else if (type === "json") {
        input = document.createElement("textarea");
        input.value = JSON.stringify(row[key]);
      } else {
        input = document.createElement("input");
        input.type = type;
        input.value = row[key];
      }
      input.dataset.row = String(rowIndex);
      input.dataset.field = key;
      input.addEventListener("change", () => {
        try {
          row[key] = parseInput(input, type);
          input.setCustomValidity("");
          onChange();
        } catch {
          input.setCustomValidity("Enter valid JSON, for example [\"F1\",\"F2\"]");
          input.reportValidity();
        }
      });
      td.append(input);
      tr.append(td);
    }
    tbody.append(tr);
  });
  table.append(thead, tbody);
  container.append(table);
}

