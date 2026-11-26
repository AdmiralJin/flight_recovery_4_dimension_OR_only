const OWNER_ORDER = ["SRM", "ARM", "CRM", "PRM"];
const COST_TRANSLATIONS = {
  flight_delay_per_minute: ["每分钟航班延误成本", "用于起飞延误分钟数的 SRM 可执行测试权重；论文将重定时嵌入航班串，但表 2 将机型—航班串分配成本设为零。"],
  flight_cancellation: ["航班取消成本", "保留论文中的量级作为抽象测试成本值，不主张其代表当前航空公司的实际货币成本。"],
  aircraft_reassignment: ["飞机改派成本", "将论文 Benchmark 中单架飞机分配成本为零的设定映射至固定列测试约定。"],
  crew_reassignment: ["机组改派成本", "将论文 Benchmark 中机组配对分配成本为零的设定映射至固定列测试约定。"],
  passenger_delay_per_pax_minute: ["每名旅客每分钟延误成本", "在项目约定中按旅客—分钟计取。"],
  unserved_passenger: ["每名未承运旅客成本", "保留论文中的量级作为抽象测试成本值。"],
  origin_change: ["始发站变更成本", "仅用于透明测试的固定惩罚；论文未提供对应系数。"],
  destination_change: ["目的站变更成本", "仅用于透明测试的固定惩罚；论文未提供对应系数。"],
  ferry_per_minute: ["每分钟调机成本", "仅用于透明测试的费率；论文 Benchmark 未公布按分钟计取的调机系数。"],
  deadhead_per_minute: ["每分钟加机组成本", "论文给出每个 DEADHEAD 航班 1,000、返回基地 2,000，而非按分钟费率；此值仅用于测试，不得归因于表 2。"],
};
const UNIT_LABELS = {
  flight_minute: "航班·分钟",
  cancelled_flight: "取消航班",
  aircraft_reassignment: "飞机改派",
  crew_reassignment: "机组改派",
  passenger_minute: "旅客·分钟",
  unserved_passenger: "未承运旅客",
  origin_change: "始发站变更",
  destination_change: "目的站变更",
  ferry_minute: "调机·分钟",
  deadhead_minute: "加机组·分钟",
};

const clone = (value) => structuredClone(value);

export function parseCostOverride(rawValue) {
  if (String(rawValue).trim() === "") return null;
  const value = Number(rawValue);
  if (!Number.isFinite(value) || value < 0) {
    throw new Error("覆盖值必须是有限的非负数。");
  }
  return value;
}

export function buildEffectiveCostProfile(baseline, overrides) {
  const effective = clone(baseline);
  for (const [key, value] of Object.entries(overrides)) {
    if (!(key in effective.coefficients)) throw new Error(`未知的成本系数：${key}`);
    const parsed = parseCostOverride(value);
    if (parsed === null) continue;
    effective.coefficients[key].value = parsed;
  }
  return effective;
}

export function buildCostRows(baseline, overrides = {}) {
  const effective = buildEffectiveCostProfile(baseline, overrides);
  return Object.entries(baseline.coefficients).map(([key, coefficient]) => ({
    key,
    meaning: COST_TRANSLATIONS[key]?.[0] || key.replaceAll("_", " "),
    baseline: coefficient.value,
    override: Object.hasOwn(overrides, key) ? overrides[key] : null,
    effective: effective.coefficients[key].value,
    unit: coefficient.unit,
    owner: coefficient.owner,
    source: coefficient.source,
    sourceReference: coefficient.source_reference,
    notes: COST_TRANSLATIONS[key]?.[1] || coefficient.notes,
  }));
}

export function buildWorkbenchConfig(
  scenario,
  costBaseline,
  costOverrides,
  capacityProfileSummary,
  modelProfile = "phase2_fixed_column",
) {
  return {
    scenario: clone(scenario),
    cost_profile_id: costBaseline.cost_profile_id,
    cost_overrides: clone(costOverrides),
    capacity_profile_id: capacityProfileSummary.capacity_profile_id,
    model_profile: modelProfile,
  };
}

function badge(text, className) {
  const element = document.createElement("span");
  element.className = `metadata-badge ${className}`;
  element.textContent = text;
  return element;
}

function sourceBadge(source) {
  return source === "petersen_2010_table_2"
    ? badge("论文参数", "is-paper")
    : badge("实现假设", "is-assumption");
}

function renderOwnerTable(owner, rows, overrides, onOverride) {
  const section = document.createElement("section");
  section.className = "cost-owner-section";
  const heading = document.createElement("div");
  heading.className = "owner-heading";
  const title = document.createElement("h3");
  title.textContent = owner;
  const count = document.createElement("span");
  count.textContent = `${rows.length} 个系数`;
  heading.append(title, count);
  section.append(heading);

  const tableWrap = document.createElement("div");
  tableWrap.className = "audit-table-wrap";
  const table = document.createElement("table");
  table.className = "cost-table";
  table.innerHTML = "<thead><tr><th>系数</th><th>含义</th><th>基线值</th><th>覆盖值</th><th>生效值</th><th>单位</th><th>来源</th></tr></thead>";
  const tbody = document.createElement("tbody");
  for (const row of rows) {
    const tr = document.createElement("tr");
    const keyCell = document.createElement("td");
    const details = document.createElement("details");
    const summary = document.createElement("summary");
    summary.textContent = row.key;
    const metadata = document.createElement("dl");
    metadata.className = "compact-metadata";
    for (const [label, value] of [
      ["归属模型", row.owner], ["来源", row.source],
      ["来源引用", row.sourceReference], ["说明", row.notes || "—"],
    ]) {
      const dt = document.createElement("dt");
      dt.textContent = label;
      const dd = document.createElement("dd");
      dd.textContent = value;
      metadata.append(dt, dd);
    }
    details.append(summary, metadata);
    keyCell.append(details);
    const meaning = document.createElement("td");
    meaning.textContent = row.meaning;
    const baseline = document.createElement("td");
    baseline.className = "numeric-cell";
    baseline.textContent = String(row.baseline);
    const overrideCell = document.createElement("td");
    const input = document.createElement("input");
    input.type = "number";
    input.min = "0";
    input.step = "any";
    input.value = row.override ?? "";
    input.placeholder = "使用基线值";
    input.setAttribute("aria-label", `覆盖成本系数 ${row.key}`);
    input.addEventListener("change", () => onOverride(row.key, input.value, input));
    overrideCell.append(input);
    const effective = document.createElement("td");
    effective.className = "numeric-cell effective-value";
    effective.textContent = String(row.effective);
    const unit = document.createElement("td");
    unit.textContent = UNIT_LABELS[row.unit.replace("cost_unit_per_", "")] || row.unit.replace("cost_unit_", "");
    const source = document.createElement("td");
    source.className = "badge-stack";
    source.append(sourceBadge(row.source));
    if (Object.hasOwn(overrides, row.key)) source.append(badge("用户覆盖值", "is-override"));
    tr.append(keyCell, meaning, baseline, overrideCell, effective, unit, source);
    tbody.append(tr);
  }
  table.append(tbody);
  tableWrap.append(table);
  section.append(tableWrap);
  return section;
}

export function renderCosts(container, baseline, overrides, onOverride) {
  container.replaceChildren();
  const rows = buildCostRows(baseline, overrides);
  for (const owner of OWNER_ORDER) {
    container.append(renderOwnerTable(
      owner,
      rows.filter((row) => row.owner === owner),
      overrides,
      onOverride,
    ));
  }
}
