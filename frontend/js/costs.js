const OWNER_ORDER = ["SRM", "ARM", "CRM", "PRM"];

const clone = (value) => structuredClone(value);

export function parseCostOverride(rawValue) {
  if (String(rawValue).trim() === "") return null;
  const value = Number(rawValue);
  if (!Number.isFinite(value) || value < 0) {
    throw new Error("Override must be a finite non-negative number.");
  }
  return value;
}

export function buildEffectiveCostProfile(baseline, overrides) {
  const effective = clone(baseline);
  for (const [key, value] of Object.entries(overrides)) {
    if (!(key in effective.coefficients)) throw new Error(`Unknown cost coefficient: ${key}`);
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
    meaning: key.replaceAll("_", " "),
    baseline: coefficient.value,
    override: Object.hasOwn(overrides, key) ? overrides[key] : null,
    effective: effective.coefficients[key].value,
    unit: coefficient.unit,
    owner: coefficient.owner,
    source: coefficient.source,
    sourceReference: coefficient.source_reference,
    notes: coefficient.notes,
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
    ? badge("PAPER", "is-paper")
    : badge("IMPLEMENTATION ASSUMPTION", "is-assumption");
}

function renderOwnerTable(owner, rows, overrides, onOverride) {
  const section = document.createElement("section");
  section.className = "cost-owner-section";
  const heading = document.createElement("div");
  heading.className = "owner-heading";
  const title = document.createElement("h3");
  title.textContent = owner;
  const count = document.createElement("span");
  count.textContent = `${rows.length} coefficients`;
  heading.append(title, count);
  section.append(heading);

  const tableWrap = document.createElement("div");
  tableWrap.className = "audit-table-wrap";
  const table = document.createElement("table");
  table.className = "cost-table";
  table.innerHTML = "<thead><tr><th>Coefficient</th><th>Meaning</th><th>Baseline</th><th>Override</th><th>Effective</th><th>Unit</th><th>Source</th></tr></thead>";
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
      ["Owner", row.owner], ["Source", row.source],
      ["Reference", row.sourceReference], ["Notes", row.notes || "—"],
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
    input.placeholder = "baseline";
    input.setAttribute("aria-label", `Override ${row.key}`);
    input.addEventListener("change", () => onOverride(row.key, input.value, input));
    overrideCell.append(input);
    const effective = document.createElement("td");
    effective.className = "numeric-cell effective-value";
    effective.textContent = String(row.effective);
    const unit = document.createElement("td");
    unit.textContent = row.unit.replace("cost_unit_", "");
    const source = document.createElement("td");
    source.className = "badge-stack";
    source.append(sourceBadge(row.source));
    if (Object.hasOwn(overrides, row.key)) source.append(badge("USER OVERRIDE", "is-override"));
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
