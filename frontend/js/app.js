import {
  loadCanonicalCosts,
  loadCase,
  loadCaseCatalog,
  checkSolveReadiness,
  solveRecovery,
  loadConstraintRegistry,
  runConstraintPrecheck,
  validateCostOverrides,
  validateScenario,
} from "./api.js";
import {
  advanceInputRevision,
  buildCurrentSolveBundle,
  capacityProfileSummary,
  createCurrentCase,
  recordSolvedRevision,
  resetCurrentCaseInputs,
} from "./case-state.js";
import {
  buildEffectiveCostProfile,
  parseCostOverride,
  renderCosts,
} from "./costs.js";
import {
  renderCapacityProfileSummary,
  renderConstraintInspector,
} from "./constraints.js";
import { showClientError, showValidation } from "./results.js";
import { renderRecovery } from "./recovery.js";
import { blankRow, renderEditor, sections } from "./tables.js";
import {
  renderVisualization,
  renderVisualizationBlocked,
  renderVisualizationLoading,
} from "./visualization.js";

const clone = (value) => structuredClone(value);

const workbenchState = {
  caseCatalog: null,
  currentCase: null,
  scenario: null,
  scenarioBaseline: null,
  scenarioValidation: null,
  costBaseline: null,
  costOverrides: {},
  costOverridesBaseline: {},
  costEffective: null,
  costValidation: "baseline",
  constraintMetadata: [],
  constraintPrecheck: null,
  recoveryColumns: null,
  recoveryColumnsBaseline: null,
  passengerCapacityProfile: null,
  passengerCapacityProfileBaseline: null,
  capacityProfileSummary: null,
  modelProfile: "phase2_fixed_column",
  solveBundle: null,
  solveReadiness: null,
  recoveredResult: null,
  resultScenario: null,
  resultInputSnapshot: null,
  resultCase: null,
  solveError: null,
  solving: false,
  inputRevision: 0,
  resultRevision: null,
  resultState: "none",
  recoverySortDelay: false,
};

let activeSection = "scenario";
let activeView = "data";
let visualizationRequestId = 0;
let precheckRequestId = 0;
let solveReadinessRequestId = 0;
let solveRequestId = 0;
let validationRequestId = 0;
let costValidationRequestId = 0;
let initializingWorkbench = false;

const editor = document.querySelector("#editor");
const tabs = document.querySelector("#tabs");
const actions = document.querySelector("#table-actions");
const viewElements = {
  data: document.querySelector("#data-view"),
  visualization: document.querySelector("#visualization-view"),
  recovery: document.querySelector("#recovery-view"),
  costs: document.querySelector("#costs-view"),
  constraints: document.querySelector("#constraints-view"),
};
const viewButtons = {
  data: document.querySelector("#show-data-view"),
  visualization: document.querySelector("#show-visualization-view"),
  recovery: document.querySelector("#show-recovery-view"),
  costs: document.querySelector("#show-costs-view"),
  constraints: document.querySelector("#show-constraints-view"),
};

function selectedRowIndex() {
  const selected = document.querySelector('input[name="selected-row"]:checked');
  return selected ? Number(selected.value) : -1;
}

function scenarioIsModified() {
  return workbenchState.scenarioBaseline
    && JSON.stringify(workbenchState.scenario) !== JSON.stringify(workbenchState.scenarioBaseline);
}

function currentCaseState() {
  return {
    metadata: workbenchState.currentCase,
    scenario: workbenchState.scenario,
    scenarioBaseline: workbenchState.scenarioBaseline,
    solveBundle: workbenchState.solveBundle,
    recoveryColumns: workbenchState.recoveryColumns,
    recoveryColumnsBaseline: workbenchState.recoveryColumnsBaseline,
    capacityProfile: workbenchState.passengerCapacityProfile,
    capacityProfileBaseline: workbenchState.passengerCapacityProfileBaseline,
    costOverrides: workbenchState.costOverrides,
    costOverridesBaseline: workbenchState.costOverridesBaseline,
    inputRevision: workbenchState.inputRevision,
    resultRevision: workbenchState.resultRevision,
    resultState: workbenchState.resultState,
  };
}

function syncCaseState(state) {
  workbenchState.scenario = state.scenario;
  workbenchState.scenarioBaseline = state.scenarioBaseline;
  workbenchState.solveBundle = state.solveBundle;
  workbenchState.recoveryColumns = state.recoveryColumns;
  workbenchState.recoveryColumnsBaseline = state.recoveryColumnsBaseline;
  workbenchState.passengerCapacityProfile = state.capacityProfile;
  workbenchState.passengerCapacityProfileBaseline = state.capacityProfileBaseline;
  workbenchState.costOverrides = state.costOverrides;
  workbenchState.costOverridesBaseline = state.costOverridesBaseline;
  workbenchState.inputRevision = state.inputRevision;
  workbenchState.resultRevision = state.resultRevision;
  workbenchState.resultState = state.resultState;
}

function updateSummary() {
  const state = workbenchState.scenario;
  if (!state) return;
  const total = ["airports", "flights", "aircraft", "crew", "passengers", "airport_intervals", "disruptions"]
    .reduce((sum, key) => sum + state[key].length, 0);
  const scenarioStatus = workbenchState.scenarioValidation === "valid"
    ? "有效"
    : workbenchState.scenarioValidation === "invalid" ? "无效"
    : scenarioIsModified() ? "已修改" : "尚未检查";
  document.querySelector("#record-summary").textContent = `${scenarioStatus} · ${state.scenario_id} · ${total} 条记录`;
  document.querySelector("#case-summary").textContent = `${workbenchState.currentCase?.label || "已导入"} · 修订版 r${workbenchState.inputRevision}`;
  const readiness = workbenchState.solveReadiness;
  document.querySelector("#solve-input-summary").textContent = readiness
    ? readiness.solve_ready ? "已就绪 · 可行性未知" : "未就绪"
    : "尚未检查";
  document.querySelector("#solver-summary-status").textContent = workbenchState.solving
    ? "正在精确求解"
    : workbenchState.solveError ? "错误" : "空闲";
  const resultLabels = {
    none: "无",
    current: `${workbenchState.recoveredResult?.status || "当前结果"} · 修订版 r${workbenchState.resultRevision}`,
    stale: `已过期 · 基于修订版 r${workbenchState.resultRevision} 求解`,
  };
  document.querySelector("#result-summary-status").textContent = resultLabels[workbenchState.resultState];
  updateWorkflow();
}

function updateWorkflow() {
  const stages = [...document.querySelectorAll(".workflow-rail span")];
  stages.forEach((stage) => { stage.className = ""; });
  if (!workbenchState.scenario) return;
  stages[0]?.classList.add("is-complete");
  if (workbenchState.scenarioValidation === "valid") stages[1]?.classList.add("is-complete");
  else if (workbenchState.scenarioValidation === "invalid") stages[1]?.classList.add("is-warning");
  else stages[1]?.classList.add("is-current");
  if (workbenchState.solveReadiness?.solve_ready) stages[2]?.classList.add("is-complete");
  else if (workbenchState.solveReadiness) stages[2]?.classList.add("is-warning");
  if (workbenchState.solving) stages[3]?.classList.add("is-current");
  else if (workbenchState.resultState !== "none") stages[3]?.classList.add("is-complete");
  if (workbenchState.resultState === "current") stages[4]?.classList.add("is-complete");
  else if (workbenchState.resultState === "stale") stages[4]?.classList.add("is-warning");
}

function markScenarioChanged() {
  workbenchState.scenarioValidation = null;
  workbenchState.constraintPrecheck = null;
  markInputsChanged();
  refreshSolveReadiness();
  updateSummary();
  renderTabs();
}

function currentSolveBundle() {
  return buildCurrentSolveBundle(currentCaseState());
}

function updateSolveButton() {
  const button = document.querySelector("#solve-recovery");
  const ready = workbenchState.solveReadiness?.solve_ready && !workbenchState.solving;
  button.disabled = !ready;
  button.textContent = workbenchState.solving ? "正在求解…" : "求解";
  const status = document.querySelector("#solve-status");
  if (!status) return;
  if (workbenchState.solving) status.textContent = "正在精确求解恢复方案…";
  else if (workbenchState.solveError) status.textContent = `求解失败：${workbenchState.solveError}`;
  else if (!workbenchState.solveReadiness?.solve_ready) {
    const missing = [
      ...(workbenchState.solveReadiness?.missing_inputs || ["请加载完整的 Solve Bundle"]),
      ...(workbenchState.solveReadiness?.invalid_profiles || []),
    ];
    status.textContent = `尚未满足求解条件：${missing.join("；")}`;
  } else if (workbenchState.resultState === "stale") status.textContent = `结果已过期：结果来自修订版 ${workbenchState.resultRevision}；请对修订版 ${workbenchState.inputRevision} 重新求解。`;
  else if (workbenchState.recoveredResult) status.textContent = `求解器状态：${workbenchState.recoveredResult.status}`;
  else status.textContent = "已满足求解输入条件 · 输入就绪不等同于优化模型可行。";
}

function clearRecovery() {
  solveRequestId += 1;
  workbenchState.recoveredResult = null;
  workbenchState.resultScenario = null;
  workbenchState.resultInputSnapshot = null;
  workbenchState.resultCase = null;
  workbenchState.solveError = null;
  workbenchState.solveReadiness = null;
  workbenchState.resultRevision = null;
  workbenchState.resultState = "none";
  document.querySelector("#export-recovered-result").disabled = true;
  updateSolveButton();
}

function markInputsChanged() {
  solveRequestId += 1;
  validationRequestId += 1;
  costValidationRequestId += 1;
  const state = currentCaseState();
  advanceInputRevision(state);
  syncCaseState(state);
  workbenchState.solveError = null;
  workbenchState.solveReadiness = null;
  document.querySelector("#export-recovered-result").disabled = true;
  updateSolveButton();
}

async function refreshSolveReadiness() {
  const requestId = ++solveReadinessRequestId;
  const bundle = currentSolveBundle();
  try {
    const readiness = await checkSolveReadiness(bundle || { scenario: clone(workbenchState.scenario) });
    if (requestId !== solveReadinessRequestId) return;
    workbenchState.solveReadiness = readiness;
  } catch (error) {
    if (requestId !== solveReadinessRequestId) return;
    workbenchState.solveReadiness = { solve_ready: false, missing_inputs: [error.message] };
  }
  updateSolveButton();
  updateSummary();
}

function openRecovery() {
  activeView = "recovery";
  renderShell();
  const container = document.querySelector("#recovery-container");
  renderRecovery(
    container, workbenchState.resultScenario || workbenchState.scenario,
    workbenchState.recoveredResult,
    document.querySelector("#recovery-mode").value,
    workbenchState.recoverySortDelay,
  );
  if (workbenchState.resultState === "stale") {
    const warning = document.createElement("p");
    warning.className = "stale-result-banner";
    warning.textContent = `结果已过期——当前输入为修订版 ${workbenchState.inputRevision}，但该结果基于修订版 ${workbenchState.resultRevision} 求解。请在审计或导出前重新求解。`;
    container.prepend(warning);
  }
  updateSolveButton();
}

async function runSolve() {
  if (workbenchState.solving) return;
  const requestId = ++solveRequestId;
  workbenchState.solving = true;
  updateSolveButton();
  updateSummary();
  try {
    await refreshSolveReadiness();
    if (requestId !== solveRequestId) return;
    if (!workbenchState.solveReadiness?.solve_ready) {
      openRecovery();
      return;
    }
    const submission = {
      caseId: workbenchState.currentCase?.case_id || null,
      inputRevision: workbenchState.inputRevision,
      scenario: clone(workbenchState.scenario),
      bundle: currentSolveBundle(),
    };
    const result = await solveRecovery(submission.bundle);
    const currentStillMatches = requestId === solveRequestId
      && submission.caseId === (workbenchState.currentCase?.case_id || null)
      && submission.inputRevision === workbenchState.inputRevision
      && JSON.stringify(submission.bundle) === JSON.stringify(currentSolveBundle());
    if (!currentStillMatches) {
      showClientError("求解已完成，但当前 Case 或输入已改变；旧响应未写入当前结果。请从当前输入重新求解。");
      return;
    }
    workbenchState.recoveredResult = result;
    workbenchState.resultScenario = submission.scenario;
    workbenchState.resultInputSnapshot = submission.bundle;
    workbenchState.resultCase = clone(workbenchState.currentCase);
    const state = currentCaseState();
    recordSolvedRevision(state);
    syncCaseState(state);
    document.querySelector("#export-recovered-result").disabled = false;
    openRecovery();
  } catch (error) {
    workbenchState.recoveredResult = null;
    workbenchState.solveError = error.message;
    workbenchState.resultRevision = null;
    workbenchState.resultState = "none";
    openRecovery();
    showClientError(error.message);
  } finally {
    workbenchState.solving = false;
    updateSolveButton();
    updateSummary();
  }
}

function renderTabs() {
  const state = workbenchState.scenario;
  if (!state) return;
  tabs.replaceChildren();
  for (const section of sections) {
    const button = document.createElement("button");
    button.className = "tab";
    button.setAttribute("role", "tab");
    button.setAttribute("aria-selected", String(section.key === activeSection));
    button.textContent = section.label;
    if (section.key !== "scenario") {
      const count = document.createElement("span");
      count.className = "tab-count";
      count.textContent = state[section.key].length;
      button.append(count);
    }
    button.addEventListener("click", () => {
      activeSection = section.key;
      renderDataView();
    });
    tabs.append(button);
  }
}

function renderShell() {
  for (const [view, element] of Object.entries(viewElements)) {
    const active = view === activeView;
    element.hidden = !active;
    viewButtons[view].setAttribute("aria-pressed", String(active));
  }
  updateSummary();
}

function renderDataView() {
  const state = workbenchState.scenario;
  if (!state) return;
  const meta = sections.find((section) => section.key === activeSection);
  document.querySelector("#section-kicker").textContent = meta.label.toUpperCase();
  document.querySelector("#section-title").textContent = meta.title;
  actions.hidden = activeSection === "scenario";
  renderTabs();
  renderEditor(editor, activeSection, state, markScenarioChanged);
  updateSummary();
}

function showDataView(section = activeSection) {
  visualizationRequestId += 1;
  precheckRequestId += 1;
  activeSection = section;
  activeView = "data";
  renderShell();
  renderDataView();
}

async function openVisualization() {
  if (!workbenchState.scenario) return;
  activeView = "visualization";
  renderShell();
  renderVisualizationLoading();
  const requestId = ++visualizationRequestId;
  try {
    const result = await validateScenario(workbenchState.scenario);
    if (requestId !== visualizationRequestId || activeView !== "visualization") return;
    workbenchState.scenarioValidation = result.valid ? "valid" : "invalid";
    showValidation(result);
    updateSummary();
    if (!result.valid) {
      renderVisualizationBlocked(result, showDataView);
      return;
    }
    renderVisualization(
      result.normalized_data,
      workbenchState.resultState === "current" ? workbenchState.recoveredResult : null,
    );
  } catch (error) {
    if (requestId !== visualizationRequestId || activeView !== "visualization") return;
    const result = { valid: false, errors: [{ location: "$", message: error.message }] };
    showClientError(error.message);
    renderVisualizationBlocked(result, showDataView);
  }
}

function setCostStatus(status, message = "") {
  workbenchState.costValidation = status;
  const badge = document.querySelector("#cost-status-badge");
  const labels = { baseline: "基线", modified: "已修改", valid: "有效", invalid: "无效" };
  badge.textContent = labels[status];
  badge.className = `badge ${status === "valid" ? "success" : status === "invalid" ? "error" : "neutral"}`;
  document.querySelector("#cost-validation-message").textContent = message;
  updateSummary();
}

function handleCostOverride(key, rawValue, input) {
  try {
    const value = parseCostOverride(rawValue);
    if (value === null) delete workbenchState.costOverrides[key];
    else workbenchState.costOverrides[key] = value;
    workbenchState.costEffective = buildEffectiveCostProfile(
      workbenchState.costBaseline,
      workbenchState.costOverrides,
    );
    markInputsChanged();
    refreshSolveReadiness();
    input.setCustomValidity("");
    setCostStatus(
      Object.keys(workbenchState.costOverrides).length ? "modified" : "baseline",
      "请运行成本校验，以确认当前浏览器覆盖值符合后端数据约定。",
    );
    renderCostView();
  } catch (error) {
    input.setCustomValidity(error.message);
    input.reportValidity();
    setCostStatus("invalid", error.message);
  }
}

function renderCostView() {
  if (!workbenchState.costBaseline) return;
  renderCosts(
    document.querySelector("#costs-container"),
    workbenchState.costBaseline,
    workbenchState.costOverrides,
    handleCostOverride,
  );
}

function openCosts() {
  visualizationRequestId += 1;
  precheckRequestId += 1;
  activeView = "costs";
  renderShell();
  renderCostView();
}

function setPrecheckStatus(precheck) {
  const badge = document.querySelector("#precheck-status-badge");
  if (!precheck) {
    badge.textContent = "尚未检查";
    badge.className = "badge neutral";
    return;
  }
  const labels = { passed: "预检查通过", warning: "预检查警告", failed: "预检查失败" };
  badge.textContent = labels[precheck.overall_status];
  badge.className = `badge ${precheck.overall_status === "passed" ? "success" : precheck.overall_status === "failed" ? "error" : "warning"}`;
}

function renderConstraints() {
  if (!workbenchState.constraintMetadata.length) return;
  renderCapacityProfileSummary(
    document.querySelector("#capacity-profile-summary"),
    workbenchState.capacityProfileSummary,
  );
  renderConstraintInspector(
    document.querySelector("#constraints-container"),
    workbenchState.constraintMetadata,
    workbenchState.constraintPrecheck,
    showDataView,
  );
  setPrecheckStatus(workbenchState.constraintPrecheck);
}

async function runPrecheck() {
  const requestId = ++precheckRequestId;
  const button = document.querySelector("#run-precheck");
  button.disabled = true;
  button.textContent = "正在检查…";
  try {
    const result = await runConstraintPrecheck(
      workbenchState.scenario,
      workbenchState.recoveryColumns,
      workbenchState.passengerCapacityProfile,
    );
    if (requestId !== precheckRequestId) return;
    workbenchState.constraintPrecheck = result;
    renderConstraints();
    updateSummary();
  } catch (error) {
    if (requestId !== precheckRequestId) return;
    setPrecheckStatus({ overall_status: "failed" });
    showClientError(error.message);
  } finally {
    if (requestId === precheckRequestId) {
      button.disabled = false;
      button.textContent = "运行预检查";
    }
  }
}

async function openConstraints() {
  visualizationRequestId += 1;
  activeView = "constraints";
  renderShell();
  renderConstraints();
  await runPrecheck();
}

function caseMetadata(caseId) {
  return workbenchState.caseCatalog?.cases.find((item) => item.case_id === caseId) || null;
}

function updateCaseDescription(metadata) {
  document.querySelector("#case-description").textContent = metadata
    ? `${metadata.description} · ${metadata.tags.join(" · ")}`
    : "导入的数据不属于内置 Case 目录。";
}

function renderCaseCatalog(catalog) {
  const selector = document.querySelector("#case-selector");
  selector.replaceChildren();
  const groups = new Map();
  for (const item of catalog.cases) {
    if (!groups.has(item.category)) groups.set(item.category, []);
    groups.get(item.category).push(item);
  }
  for (const [label, items] of groups) {
    const group = document.createElement("optgroup");
    group.label = label;
    for (const item of items) {
      const option = document.createElement("option");
      option.value = item.case_id;
      option.textContent = item.label;
      group.append(option);
    }
    selector.append(group);
  }
  selector.value = catalog.default_case_id;
  updateCaseDescription(caseMetadata(catalog.default_case_id));
}

async function applyCasePayload(payload) {
  const state = createCurrentCase(payload);
  const validation = await validateScenario(state.scenario);
  const readiness = await checkSolveReadiness(
    buildCurrentSolveBundle(state) || { scenario: clone(state.scenario) },
  );
  workbenchState.currentCase = state.metadata;
  syncCaseState(state);
  workbenchState.costEffective = buildEffectiveCostProfile(workbenchState.costBaseline, workbenchState.costOverrides);
  workbenchState.capacityProfileSummary = capacityProfileSummary(workbenchState.passengerCapacityProfile);
  workbenchState.scenarioValidation = validation.valid ? "valid" : "invalid";
  workbenchState.solveReadiness = readiness;
  showValidation(validation);
  workbenchState.constraintPrecheck = null;
  setCostStatus(
    Object.keys(workbenchState.costOverrides).length ? "modified" : "baseline",
    "已从当前 Case 的基线载入。",
  );
  clearRecovery();
  activeSection = "scenario";
  updateCaseDescription(workbenchState.currentCase);
  updateSolveButton();
  updateSummary();
  if (activeView === "visualization") await openVisualization();
  else if (activeView === "constraints") await openConstraints();
  else if (activeView === "recovery") openRecovery();
  else {
    renderShell();
    if (activeView === "data") renderDataView();
    else renderCostView();
  }
}

async function loadCatalogCase(caseId) {
  const button = document.querySelector("#load-case");
  button.disabled = true;
  button.textContent = "正在加载…";
  try {
    await applyCasePayload(await loadCase(caseId));
  } catch (error) {
    document.querySelector("#case-summary").textContent = "Case 加载失败";
    document.querySelector("#case-description").textContent = `无法加载所选 Case。${error.message}`;
    showClientError(`Case 加载失败：${error.message}`);
  } finally {
    button.disabled = false;
    button.textContent = "加载 Case";
  }
}

async function initializeWorkbench() {
  if (initializingWorkbench) return;
  initializingWorkbench = true;
  const button = document.querySelector("#load-case");
  const selector = document.querySelector("#case-selector");
  button.disabled = true;
  button.textContent = "正在加载…";
  selector.disabled = true;
  document.querySelector("#case-summary").textContent = "正在加载目录…";
  try {
    const [catalog, costs, registry] = await Promise.all([
      loadCaseCatalog(),
      loadCanonicalCosts(),
      loadConstraintRegistry(),
    ]);
    workbenchState.caseCatalog = catalog;
    workbenchState.costBaseline = costs;
    workbenchState.costEffective = clone(costs);
    workbenchState.constraintMetadata = registry.constraints;
    workbenchState.modelProfile = registry.model_profile;
    renderCaseCatalog(catalog);
    selector.disabled = false;
    await loadCatalogCase(catalog.default_case_id);
  } catch (error) {
    workbenchState.caseCatalog = null;
    document.querySelector("#case-summary").textContent = "目录不可用";
    document.querySelector("#case-description").textContent = `初始化失败。请点击“重试初始化”。${error.message}`;
    button.disabled = false;
    button.textContent = "重试初始化";
    showClientError(`工作台初始化失败：${error.message}`);
  } finally {
    initializingWorkbench = false;
    if (workbenchState.caseCatalog) {
      button.disabled = false;
      button.textContent = "加载 Case";
    }
  }
}

function downloadJson(payload, filename) {
  const blob = new Blob([`${JSON.stringify(payload, null, 2)}\n`], { type: "application/json" });
  const link = document.createElement("a");
  link.href = URL.createObjectURL(blob);
  link.download = filename;
  link.click();
  URL.revokeObjectURL(link.href);
}

viewButtons.data.addEventListener("click", () => showDataView());
viewButtons.visualization.addEventListener("click", openVisualization);
viewButtons.recovery.addEventListener("click", openRecovery);
viewButtons.costs.addEventListener("click", openCosts);
viewButtons.constraints.addEventListener("click", openConstraints);
document.querySelector("#case-selector").addEventListener("change", (event) => {
  updateCaseDescription(caseMetadata(event.target.value));
});
document.querySelector("#load-case").addEventListener("click", () => {
  if (!workbenchState.caseCatalog) initializeWorkbench();
  else loadCatalogCase(document.querySelector("#case-selector").value);
});
document.querySelector("#solve-recovery").addEventListener("click", runSolve);
document.querySelector("#recovery-mode").addEventListener("change", openRecovery);
document.querySelector("#recovery-container").addEventListener("click", (event) => {
  if (event.target.id !== "sort-recovery-delay") return;
  workbenchState.recoverySortDelay = !workbenchState.recoverySortDelay;
  openRecovery();
});
document.querySelector("#export-recovered-result").addEventListener("click", () => {
  if (workbenchState.recoveredResult) downloadJson(
    workbenchState.recoveredResult,
    `${workbenchState.scenario.scenario_id}_recovered_result.json`,
  );
});
document.querySelector("#reset-current-case").addEventListener("click", () => {
  const state = currentCaseState();
  resetCurrentCaseInputs(state);
  syncCaseState(state);
  workbenchState.scenarioValidation = null;
  workbenchState.constraintPrecheck = null;
  workbenchState.costEffective = buildEffectiveCostProfile(workbenchState.costBaseline, workbenchState.costOverrides);
  workbenchState.capacityProfileSummary = capacityProfileSummary(workbenchState.passengerCapacityProfile);
  refreshSolveReadiness();
  setCostStatus("baseline", "Scenario、求解列、容量、配置及成本覆盖值均已恢复至此 Case 的基线。");
  if (activeView === "data") renderDataView();
  else if (activeView === "visualization") openVisualization();
  else if (activeView === "constraints") openConstraints();
  else if (activeView === "recovery") openRecovery();
  else renderCostView();
});
document.querySelector("#reset-section").addEventListener("click", () => {
  const key = activeSection;
  if (key === "scenario") {
    workbenchState.scenario.scenario_id = workbenchState.scenarioBaseline.scenario_id;
    workbenchState.scenario.recovery_window = clone(workbenchState.scenarioBaseline.recovery_window);
  } else {
    workbenchState.scenario[key] = clone(workbenchState.scenarioBaseline[key]);
  }
  markScenarioChanged();
  renderDataView();
});
document.querySelector("#add-row").addEventListener("click", () => {
  workbenchState.scenario[activeSection].push(blankRow(activeSection));
  markScenarioChanged();
  renderDataView();
});
document.querySelector("#duplicate-row").addEventListener("click", () => {
  const index = selectedRowIndex();
  if (index < 0) return showClientError("请先选择要复制的行。");
  workbenchState.scenario[activeSection].splice(index + 1, 0, clone(workbenchState.scenario[activeSection][index]));
  markScenarioChanged();
  renderDataView();
});
document.querySelector("#delete-row").addEventListener("click", () => {
  const index = selectedRowIndex();
  if (index < 0) return showClientError("请先选择要删除的行。");
  workbenchState.scenario[activeSection].splice(index, 1);
  markScenarioChanged();
  renderDataView();
});
document.querySelector("#validate").addEventListener("click", async () => {
  if (activeView === "visualization") return openVisualization();
  if (activeView === "constraints") return runPrecheck();
  if (activeView === "costs") return document.querySelector("#validate-costs").click();
  const requestId = ++validationRequestId;
  const revision = workbenchState.inputRevision;
  try {
    const result = await validateScenario(workbenchState.scenario);
    if (requestId !== validationRequestId || revision !== workbenchState.inputRevision) return;
    workbenchState.scenarioValidation = result.valid ? "valid" : "invalid";
    showValidation(result);
    updateSummary();
  } catch (error) {
    showClientError(error.message);
  }
});
document.querySelector("#validate-costs").addEventListener("click", async () => {
  const requestId = ++costValidationRequestId;
  const revision = workbenchState.inputRevision;
  try {
    const result = await validateCostOverrides({
      base_cost_profile_id: workbenchState.costBaseline.cost_profile_id,
      overrides: workbenchState.costOverrides,
    });
    if (requestId !== costValidationRequestId || revision !== workbenchState.inputRevision) return;
    workbenchState.costEffective = result.effective_profile;
    refreshSolveReadiness();
    setCostStatus("valid", `已校验 ${Object.keys(result.overrides).length} 个覆盖值；规范元数据保持不变。`);
    renderCostView();
  } catch (error) {
    setCostStatus("invalid", error.message);
  }
});
document.querySelector("#reset-cost-overrides").addEventListener("click", () => {
  workbenchState.costOverrides = clone(workbenchState.costOverridesBaseline);
  workbenchState.costEffective = buildEffectiveCostProfile(workbenchState.costBaseline, workbenchState.costOverrides);
  markInputsChanged();
  refreshSolveReadiness();
  setCostStatus("baseline", "成本覆盖值已恢复至当前 Case 的基线。");
  renderCostView();
});
document.querySelector("#run-precheck").addEventListener("click", runPrecheck);
document.querySelector("#export-scenario").addEventListener("click", () => {
  downloadJson(workbenchState.scenario, `${workbenchState.scenario.scenario_id || "scenario"}.json`);
});
document.querySelector("#export-current-case").addEventListener("click", () => {
  downloadJson({
    schema_version: "1.0.0",
    current_case: {
      metadata: clone(workbenchState.currentCase),
      input_revision: workbenchState.inputRevision,
    },
    scenario: clone(workbenchState.scenario),
    solve_input: currentSolveBundle(),
    result: {
      state: workbenchState.resultState,
      solved_revision: workbenchState.resultRevision,
      case: clone(workbenchState.resultCase),
      input_snapshot: clone(workbenchState.resultInputSnapshot),
      recovered_result: clone(workbenchState.recoveredResult),
    },
  }, `${workbenchState.currentCase?.case_id || workbenchState.scenario.scenario_id}_current_case.json`);
});

const fileInput = document.querySelector("#file-input");
let pendingImportKind = null;
document.querySelector("#import-scenario").addEventListener("click", () => {
  pendingImportKind = "scenario";
  fileInput.click();
});
document.querySelector("#import-bundle").addEventListener("click", () => {
  pendingImportKind = "bundle";
  fileInput.click();
});
fileInput.addEventListener("change", async () => {
  const [file] = fileInput.files;
  if (!file) return;
  try {
    const imported = JSON.parse(await file.text());
    const isSolveBundle = imported.schema_version === "1.0.0" && "recovery_columns" in imported;
    if (pendingImportKind === "bundle" && !isSolveBundle) {
      throw new Error("导入 Solve Bundle 时必须使用带版本号的 SolveRequest 结构。");
    }
    if (pendingImportKind === "scenario" && isSolveBundle) {
      throw new Error("该文件是 Solve Bundle。请使用“导入 Solve Bundle”，以保留其中显式定义的输入。");
    }
    if (pendingImportKind === "scenario" && ("scenario" in imported || "cost_overrides" in imported)) {
      throw new Error("导入 Scenario 时必须提供原始 Scenario JSON 文档。");
    }
    if (pendingImportKind === "bundle") {
      const readiness = await checkSolveReadiness(imported);
      if (!readiness.solve_ready) throw new Error(`Solve Bundle 尚未满足求解条件：${[...readiness.missing_inputs, ...readiness.invalid_profiles].join("；")}`);
    }
    const result = await validateScenario(pendingImportKind === "bundle" ? imported.scenario : imported);
    if (!result.valid) {
      showValidation(result);
      if (activeView === "visualization") renderVisualizationBlocked(result, showDataView);
      return;
    }
    const label = pendingImportKind === "bundle" ? "已导入的 Solve Bundle" : "已导入的 Scenario";
    await applyCasePayload({
      case: {
        case_id: `imported-${result.normalized_data.scenario_id}`,
        label,
        category: "已导入",
        description: pendingImportKind === "bundle"
          ? "用户导入的显式 Solve Bundle。"
          : "用户导入的 Scenario-only 数据；系统未推断任何求解输入。",
        tags: ["已导入", pendingImportKind === "bundle" ? "Solve Bundle" : "Scenario-only"],
        mode: pendingImportKind === "bundle" ? "solve_bundle" : "scenario_only",
        expected: null,
      },
      scenario: result.normalized_data,
      solve_bundle: pendingImportKind === "bundle" ? { ...imported, scenario: result.normalized_data } : null,
    });
    workbenchState.scenarioValidation = "valid";
    showValidation(result);
    showDataView();
  } catch (error) {
    showClientError(`导入失败：${error.message}`);
  } finally {
    fileInput.value = "";
    pendingImportKind = null;
  }
});

renderShell();
initializeWorkbench();
