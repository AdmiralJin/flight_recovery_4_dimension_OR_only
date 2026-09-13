const MODEL_ORDER = ["SRM", "ARM", "CRM", "PRM"];

export function groupConstraintMetadata(metadata) {
  return Object.fromEntries(MODEL_ORDER.map((model) => [
    model,
    metadata.filter((item) => item.model === model),
  ]));
}

export function indexPrecheckResults(precheck) {
  return new Map((precheck?.results || []).map((item) => [item.constraint_id, item]));
}

function metadataBadge(text, className) {
  const badge = document.createElement("span");
  badge.className = `metadata-badge ${className}`;
  badge.textContent = text;
  return badge;
}

function precheckBadge(result) {
  if (!result) return metadataBadge("NOT CHECKED", "is-neutral");
  const labels = {
    passed: "PRECHECK PASSED",
    warning: "PRECHECK WARNING",
    failed: "PRECHECK FAILED",
  };
  return metadataBadge(labels[result.status], `is-${result.status}`);
}

function classificationBadges(item) {
  const result = [];
  if (item.implementation_status === "proxy") {
    result.push(metadataBadge("PROXY", "is-proxy"));
  } else if (item.kind === "paper_constraint") {
    result.push(metadataBadge("PAPER", "is-paper"));
  } else if (item.kind === "fixed_column_validation") {
    result.push(metadataBadge("FIXED-COLUMN VALIDATION", "is-validation"));
  } else {
    result.push(metadataBadge("IMPLEMENTATION ASSUMPTION", "is-assumption"));
  }
  if (item.implementation_status === "deferred") {
    result.push(metadataBadge("DEFERRED", "is-deferred"));
  }
  return result;
}

function definitionList(items) {
  const list = document.createElement("dl");
  list.className = "constraint-metadata";
  for (const [term, value] of items) {
    const dt = document.createElement("dt");
    dt.textContent = term;
    const dd = document.createElement("dd");
    dd.textContent = value;
    list.append(dt, dd);
  }
  return list;
}

function constraintCard(item, check, onNavigate) {
  const card = document.createElement("article");
  card.className = `constraint-card ${item.implementation_status === "proxy" ? "is-proxy" : ""}`;
  const head = document.createElement("div");
  head.className = "constraint-card-head";
  const identity = document.createElement("div");
  const id = document.createElement("code");
  id.textContent = item.constraint_id;
  const title = document.createElement("h4");
  title.textContent = item.name;
  identity.append(id, title);
  const badges = document.createElement("div");
  badges.className = "badge-stack";
  for (const token of classificationBadges(item)) badges.append(token);
  badges.append(precheckBadge(check));
  head.append(identity, badges);

  const formula = document.createElement("code");
  formula.className = "formula-summary";
  formula.textContent = item.formula_summary;
  const meta = definitionList([
    ["Paper equation", item.paper_equation || "—"],
    ["Type", item.kind],
    ["Provenance", item.provenance],
    ["Implementation", item.implementation_status],
    ["Related inputs", item.input_dependencies.join(" · ")],
    ["Assumptions", item.assumption_refs.join(", ") || "—"],
    ["Provenance detail", item.provenance_detail],
  ]);
  const note = document.createElement("p");
  note.className = "constraint-note";
  note.textContent = item.notes;
  card.append(head, formula, meta, note);

  if (check) {
    const current = document.createElement("div");
    current.className = `current-data-summary is-${check.status}`;
    const summary = document.createElement("strong");
    summary.textContent = check.summary;
    current.append(summary);
    const values = Object.entries(check.derived_values || {});
    if (values.length) {
      const valueList = document.createElement("div");
      valueList.className = "derived-values";
      for (const [key, value] of values) {
        const chip = document.createElement("span");
        chip.textContent = `${key}: ${value}`;
        valueList.append(chip);
      }
      current.append(valueList);
    }
    if (check.issues?.length) {
      const issues = document.createElement("ul");
      for (const issue of check.issues) {
        const li = document.createElement("li");
        li.textContent = issue;
        issues.append(li);
      }
      current.append(issues);
    }
    card.append(current);
  }

  if (item.related_sections.length) {
    const navigation = document.createElement("div");
    navigation.className = "related-navigation";
    for (const section of item.related_sections) {
      const button = document.createElement("button");
      button.className = "button small";
      button.textContent = `Go to ${section.replace("airport_intervals", "Airport Capacity")}`;
      button.addEventListener("click", () => onNavigate(section));
      navigation.append(button);
    }
    card.append(navigation);
  }
  return card;
}

export function renderCapacityProfileSummary(container, summary) {
  container.replaceChildren();
  const heading = document.createElement("div");
  heading.className = "capacity-profile-head";
  const title = document.createElement("div");
  const kicker = document.createElement("strong");
  kicker.textContent = summary.display_label;
  const id = document.createElement("span");
  id.textContent = `${summary.capacity_profile_id} · ${summary.source} · ${summary.units}`;
  title.append(kicker, id);
  heading.append(title, metadataBadge("NOT AIRCRAFT PHYSICAL CAPACITY", "is-test-capacity"));
  const grid = document.createElement("div");
  grid.className = "capacity-option-grid";
  for (const [optionId, value] of Object.entries(summary.seat_capacity_by_option_id)) {
    const item = document.createElement("span");
    item.textContent = `${optionId}: ${value}`;
    grid.append(item);
  }
  const note = document.createElement("p");
  note.textContent = summary.notes.join(" ");
  container.append(heading, grid, note);
}

export function renderConstraintInspector(container, metadata, precheck, onNavigate) {
  container.replaceChildren();
  const grouped = groupConstraintMetadata(metadata);
  const checks = indexPrecheckResults(precheck);
  for (const model of MODEL_ORDER) {
    const section = document.createElement("section");
    section.className = "constraint-model-section";
    const heading = document.createElement("div");
    heading.className = "owner-heading";
    const title = document.createElement("h3");
    title.textContent = model;
    const count = document.createElement("span");
    count.textContent = `${grouped[model].length} constraints`;
    heading.append(title, count);
    const grid = document.createElement("div");
    grid.className = "constraint-card-grid";
    for (const item of grouped[model]) {
      grid.append(constraintCard(item, checks.get(item.constraint_id), onNavigate));
    }
    section.append(heading, grid);
    container.append(section);
  }
}
