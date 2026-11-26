const MODEL_ORDER = ["SRM", "ARM", "CRM", "PRM"];
const CONSTRAINT_TEXT = {
  "SRM-C01": ["航班覆盖", "每个基础航班必须选择一个显式的执飞或取消 Flight Option。"],
  "SRM-C02": ["战略航班保持", "“战略航班”是对论文约束的实现映射。"],
  "SRM-C03": ["到达容量", "采用左闭右开的机场时间区间。"],
  "SRM-C04": ["起飞容量", "采用左闭右开的机场时间区间。"],
  "SRM-C05": ["机位库存代理约束", "代理约束：采用汇总的地面飞机库存，而非机尾号级机位占用；计划在 Phase 3 重新审视。"],
  "SRM-C06": ["市场座位保持代理约束", "代理约束：保持市场服务；min_seats 并非飞机物理座位容量。计划在 Phase 3 重新审视。"],
  "ARM-C01": ["飞机航班串选择", "为每架飞机选择一个由该机尾号持有的显式固定航班串。"],
  "ARM-C02": ["必需 Flight Option 覆盖", "实际代码 ID 同时包含必需项覆盖与非必需项禁止。"],
  "ARM-C03": ["飞机终端机场", "依据论文文字说明与固定列终端机场映射。"],
  "ARM-C04": ["维修要求满足", "使用经过校验的固定列维修标志。"],
  "ARM-C05": ["固定飞机航班串可行性", "在建模前完成校验；它不是单独的论文约束。"],
  "CRM-C01": ["机组配对选择", "为每个机组选择一个由该机组持有的显式固定配对。"],
  "CRM-C02": ["执飞 Flight Option 覆盖", "采用汇总的单机组单元覆盖。"],
  "CRM-C03": ["禁止非必需 OPERATE / DEADHEAD", "实际代码 ID 同时检查执飞泄漏与 DEADHEAD 排班一致性。"],
  "CRM-C04": ["固定机组配对可行性", "不声称覆盖航空公司全部执勤 / 休息合法性规则。"],
  "CRM-C05": ["机组终端机场与所有权", "固定列终端机场保护条件，不是单独编号的论文公式。"],
  "PRM-C01": ["旅客组行程选择", "将论文中的整数旅客流映射为不可拆分旅客组的二元选择。"],
  "PRM-C02": ["旅客行程与排班一致性", "外部排班保护条件；PRM 不会重新选择 Flight Options。"],
  "PRM-C03": ["旅客座位容量", "测试容量：表示剩余测试库存而非飞机物理容量；ARM 与 PRM 的耦合计划在 Phase 3 重新审视。"],
  "PRM-C04": ["固定旅客行程可行性", "当前时间连续性检查并非真实航空公司的最小衔接时间（MCT）实现。"],
};
const ENUM_LABELS = {
  paper_constraint: "论文约束",
  implementation_guard: "实现保护条件",
  fixed_column_validation: "固定列校验",
  paper_defined: "论文定义",
  implementation_assumption: "实现假设",
  generated_provisional: "暂定生成规则",
  airline_extension: "航空公司扩展",
  implemented: "已实现",
  proxy: "代理实现",
  deferred: "暂缓实现",
};
const PRECHECK_SUMMARIES = {
  "Every flight has at least one explicit option.": "每个航班均至少具有一个显式 Flight Option。",
  "Strategic flights have operate candidates.": "所有战略航班均具有执飞候选项。",
  "Arrival-capacity buckets and option memberships were derived.": "已推导到达容量时间区间及 Flight Option 归属关系。",
  "Departure-capacity buckets and option memberships were derived.": "已推导起飞容量时间区间及 Flight Option 归属关系。",
  "Provisional aggregate gate inventory can be constructed.": "可以构建暂定的汇总机位库存。",
  "Market-service proxy inputs were counted; this is not physical seat capacity.": "已统计市场服务代理输入；该数值并非飞机物理座位容量。",
  "Each aircraft has a fixed string candidate.": "每架飞机均具有固定航班串候选项。",
  "Potential string coverage was counted; exact coverage needs an external schedule request.": "已统计潜在航班串覆盖；精确覆盖需要外部排班请求。",
  "Recovery Columns semantic validation passed.": "Recovery Columns 语义校验通过。",
  "Each crew has a fixed pairing candidate.": "每个机组均具有固定配对候选项。",
  "Potential operating coverage was counted; exact coverage needs an external schedule request.": "已统计潜在执飞覆盖；精确覆盖需要外部排班请求。",
  "OPERATE/DEADHEAD incidence is available; schedule leakage needs an external request.": "已获得 OPERATE / DEADHEAD 关联关系；排班泄漏检查需要外部请求。",
  "Each passenger group has a fixed itinerary candidate.": "每个旅客组均具有固定行程候选项。",
  "Itinerary flight references were indexed; eligibility needs an external schedule request.": "已索引行程中的航班引用；资格判定需要外部排班请求。",
  "Test residual capacity covers referenced passenger options.": "测试剩余容量覆盖了所引用的旅客 Flight Options。",
};
const CAPACITY_NOTES = {
  "Phase 2.5 implementation-only capacity available to modeled passenger groups.": "Phase 2.5 实现专用容量，仅供模型中的旅客组使用。",
  "Values are not Flight.min_seats, aircraft capacities, airline inventory, or paper data.": "这些数值不代表 Flight.min_seats、飞机物理容量、航空公司库存或论文数据。",
  "The profile represents the residual-capacity right-hand side mapped from paper equation (3.17).": "该配置表示由论文公式（3.17）映射得到的剩余容量右端项。",
};

function constraintText(constraintId) {
  return Object.entries(CONSTRAINT_TEXT)
    .find(([prefix]) => constraintId === prefix || constraintId.startsWith(`${prefix}-`))?.[1];
}

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
  if (!result) return metadataBadge("尚未检查", "is-neutral");
  const labels = {
    passed: "预检查通过",
    warning: "预检查警告",
    failed: "预检查失败",
  };
  return metadataBadge(labels[result.status], `is-${result.status}`);
}

function classificationBadges(item) {
  const result = [];
  if (item.implementation_status === "proxy") {
    result.push(metadataBadge("代理约束 PROXY", "is-proxy"));
  } else if (item.kind === "paper_constraint") {
    result.push(metadataBadge("论文约束", "is-paper"));
  } else if (item.kind === "fixed_column_validation") {
    result.push(metadataBadge("固定列校验", "is-validation"));
  } else {
    result.push(metadataBadge("实现假设", "is-assumption"));
  }
  if (item.implementation_status === "deferred") {
    result.push(metadataBadge("暂缓实现", "is-deferred"));
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
  const translated = constraintText(item.constraint_id);
  title.textContent = translated?.[0] || item.name;
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
    ["论文公式", item.paper_equation || "—"],
    ["类型", ENUM_LABELS[item.kind] || item.kind],
    ["依据来源", ENUM_LABELS[item.provenance] || item.provenance],
    ["实现状态", ENUM_LABELS[item.implementation_status] || item.implementation_status],
    ["相关输入", item.input_dependencies.join(" · ")],
    ["假设", item.assumption_refs.join(", ") || "—"],
    ["来源详情", item.provenance_detail],
  ]);
  const note = document.createElement("p");
  note.className = "constraint-note";
  note.textContent = translated?.[1] || item.notes;
  card.append(head, formula, meta, note);

  if (check) {
    const current = document.createElement("div");
    current.className = `current-data-summary is-${check.status}`;
    const summary = document.createElement("strong");
    summary.textContent = PRECHECK_SUMMARIES[check.summary] || check.summary;
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
      const sectionLabels = {
        scenario: "场景", airports: "机场", flights: "航班", aircraft: "飞机",
        crew: "机组", passengers: "旅客", airport_intervals: "机场容量", disruptions: "扰动",
      };
      button.textContent = `前往${sectionLabels[section] || section}`;
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
  const source = ENUM_LABELS[summary.source] || summary.source;
  const units = summary.units === "seats" ? "座位" : summary.units;
  id.textContent = `${summary.capacity_profile_id} · ${source} · ${units}`;
  title.append(kicker, id);
  heading.append(title, metadataBadge("非飞机物理座位容量", "is-test-capacity"));
  const grid = document.createElement("div");
  grid.className = "capacity-option-grid";
  for (const [optionId, value] of Object.entries(summary.seat_capacity_by_option_id)) {
    const item = document.createElement("span");
    item.textContent = `${optionId}: ${value}`;
    grid.append(item);
  }
  const note = document.createElement("p");
  note.textContent = summary.notes.map((item) => CAPACITY_NOTES[item] || item).join(" ");
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
    count.textContent = `${grouped[model].length} 条约束`;
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
