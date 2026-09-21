export const sections = [
  { key: "scenario", label: "场景 Scenario", title: "恢复时间窗" },
  { key: "airports", label: "机场", title: "机场主数据" },
  { key: "flights", label: "航班", title: "计划航段" },
  { key: "aircraft", label: "飞机", title: "飞机轮转" },
  { key: "crew", label: "机组", title: "驾驶舱机组配对" },
  { key: "passengers", label: "旅客", title: "旅客流（Passenger Commodities）" },
  { key: "airport_intervals", label: "机场容量", title: "时变机场容量" },
  { key: "disruptions", label: "扰动", title: "扰动事件" },
];

export const columns = {
  airports: [
    ["airport_id", "机场 ID", "text"], ["name", "名称", "text"],
  ],
  flights: [
    ["flight_id", "航班", "text"], ["origin", "始发站", "text"], ["destination", "目的站", "text"],
    ["sched_dep", "计划起飞", "text"], ["sched_arr", "计划到达", "text"], ["duration", "航程时长（分钟）", "number"],
    ["original_aircraft", "原计划飞机", "text"], ["original_equipment", "机型", "text"], ["original_crew", "原计划机组", "text"],
    ["strategic_flag", "战略航班", "boolean"], ["market_flag", "市场航班", "boolean"], ["min_seats", "最少座位数", "number"], ["max_delay", "最大延误（分钟）", "number"],
  ],
  aircraft: [
    ["tail_id", "机尾号", "text"], ["equipment_type", "机型", "text"], ["initial_station_at_t", "初始机场", "text"],
    ["required_station_at_T_end", "期末要求机场", "text"], ["maintenance_required", "需要维修", "boolean"],
    ["maintenance_stations", "维修机场", "json"], ["original_rotation", "原始轮转", "json"],
  ],
  crew: [
    ["crew_id", "机组", "text"], ["rating", "资质等级", "text"], ["start_station_at_t", "初始机场", "text"],
    ["required_station_at_T_end", "期末要求机场", "text"], ["original_duties", "原执勤任务", "json"], ["original_pairing", "原始配对", "json"],
  ],
  passengers: [
    ["pax_group_id", "旅客组", "text"], ["count", "人数", "number"], ["origin", "始发站", "text"], ["destination", "目的站", "text"],
    ["original_departure", "原计划出发", "text"], ["scheduled_arrival", "计划到达", "text"], ["original_itinerary", "原始行程", "json"],
  ],
  airport_intervals: [
    ["airport", "机场", "text"], ["start_time", "开始时间", "text"], ["end_time", "结束时间", "text"],
    ["arr_capacity", "到达容量", "number"], ["dep_capacity", "起飞容量", "number"], ["gate_capacity", "机位容量", "number"],
    ["curfew_flag", "宵禁", "boolean"], ["weather_restrictions", "天气限制", "json"],
  ],
  disruptions: [
    ["airport", "机场", "text"], ["start_time", "开始时间", "text"], ["end_time", "结束时间", "text"],
    ["capacity_change", "容量变化", "number"], ["restriction_type", "限制类型", "text"],
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
      ["start_time", "恢复开始时间", data.recovery_window.start_time],
      ["end_time", "恢复结束时间", data.recovery_window.end_time],
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
    note.textContent = "请使用 ISO 8601 时间戳。内置示例采用 UTC（Z）时间，以确保导入和导出的时间语义明确。";
    form.append(note);
    container.append(form);
    return;
  }

  const rows = data[section];
  if (!rows.length) {
    const empty = document.createElement("div");
    empty.className = "empty-state";
    empty.textContent = "当前没有记录。请选择“新增行”开始录入。";
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
    selector.setAttribute("aria-label", `选择第 ${rowIndex + 1} 行`);
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
          option.textContent = value ? "是（true）" : "否（false）";
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
          input.setCustomValidity("请输入有效的 JSON，例如 [\"F1\",\"F2\"]");
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
