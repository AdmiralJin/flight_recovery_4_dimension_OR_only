import {
  loadCanonicalCosts,
  loadBenchmarkPrecheckInputs,
  loadConstraintRegistry,
  loadExample,
  runConstraintPrecheck,
  validateCostOverrides,
  validateScenario,
} from "./api.js";
import {
  buildEffectiveCostProfile,
  buildWorkbenchConfig,
  parseCostOverride,
  renderCosts,
} from "./costs.js";
import {
  renderCapacityProfileSummary,
  renderConstraintInspector,
} from "./constraints.js";
import { showClientError, showValidation } from "./results.js";
import { blankRow, renderEditor, sections } from "./tables.js";
import {
  renderVisualization,
  renderVisualizationBlocked,
  renderVisualizationLoading,
} from "./visualization.js";

const clone = (value) => structuredClone(value);

const workbenchState = {
  scenario: null,
  scenarioBaseline: null,
  scenarioValidation: null,
  costBaseline: null,
  costOverrides: {},
  costEffective: null,
  costValidation: "baseline",
  constraintMetadata: [],
  constraintPrecheck: null,
  recoveryColumns: null,
  passengerCapacityProfile: null,
  capacityProfileSummary: null,
  modelProfile: "phase2_fixed_column",
};

let activeSection = "scenario";
let activeView = "data";
let visualizationRequestId = 0;
let precheckRequestId = 0;

const editor = document.querySelector("#editor");
const tabs = document.querySelector("#tabs");
const actions = document.querySelector("#table-actions");
const viewElements = {
  data: document.querySelector("#data-view"),
  visualization: document.querySelector("#visualization-view"),
  costs: document.querySelector("#costs-view"),
  constraints: document.querySelector("#constraints-view"),
};
const viewButtons = {
  data: document.querySelector("#show-data-view"),
  visualization: document.querySelector("#show-visualization-view"),
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

function updateSummary() {
  const state = workbenchState.scenario;
  if (!state) return;
  const total = ["airports", "flights", "aircraft", "crew", "passengers", "airport_intervals", "disruptions"]
    .reduce((sum, key) => sum + state[key].length, 0);
  const scenarioStatus = workbenchState.scenarioValidation === "valid"
    ? "Valid"
    : scenarioIsModified() ? "Modified" : "Not checked";
  document.querySelector("#record-summary").textContent = `${scenarioStatus} · ${state.scenario_id} · ${total} records`;
  const overrideCount = Object.keys(workbenchState.costOverrides).length;
  document.querySelector("#cost-summary-status").textContent = overrideCount
    ? `Modified · ${overrideCount} override${overrideCount === 1 ? "" : "s"}`
    : "Baseline";
  const precheck = workbenchState.constraintPrecheck;
  document.querySelector("#constraint-summary-status").textContent = precheck
    ? `Precheck ${precheck.overall_status}`
    : "Not checked";
}

function markScenarioChanged() {
  workbenchState.scenarioValidation = null;
  workbenchState.constraintPrecheck = null;
  updateSummary();
  renderTabs();
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
    renderVisualization(result.normalized_data);
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
  const labels = { baseline: "Baseline", modified: "Modified", valid: "Valid", invalid: "Invalid" };
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
    input.setCustomValidity("");
    setCostStatus(
      Object.keys(workbenchState.costOverrides).length ? "modified" : "baseline",
      "Validate to confirm the current browser overrides against the backend contract.",
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
    badge.textContent = "Not checked";
    badge.className = "badge neutral";
    return;
  }
  const labels = { passed: "Precheck Passed", warning: "Precheck Warning", failed: "Precheck Failed" };
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
  button.textContent = "Checking…";
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
      button.textContent = "Run Precheck";
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

async function setExample() {
  try {
    const [scenario, precheckInputs] = await Promise.all([
      loadExample(),
      loadBenchmarkPrecheckInputs(),
    ]);
    workbenchState.scenario = scenario;
    workbenchState.scenarioBaseline = clone(scenario);
    workbenchState.recoveryColumns = precheckInputs.recovery_columns;
    workbenchState.passengerCapacityProfile = precheckInputs.passenger_capacity_profile;
    workbenchState.scenarioValidation = null;
    workbenchState.constraintPrecheck = null;
    activeSection = "scenario";
    if (activeView === "visualization") await openVisualization();
    else if (activeView === "constraints") await openConstraints();
    else {
      renderShell();
      if (activeView === "data") renderDataView();
      else renderCostView();
    }
  } catch (error) {
    showClientError(error.message);
  }
}

async function initializeWorkbench() {
  try {
    const [scenario, costs, registry, precheckInputs] = await Promise.all([
      loadExample(),
      loadCanonicalCosts(),
      loadConstraintRegistry(),
      loadBenchmarkPrecheckInputs(),
    ]);
    workbenchState.scenario = scenario;
    workbenchState.scenarioBaseline = clone(scenario);
    workbenchState.costBaseline = costs;
    workbenchState.costEffective = clone(costs);
    workbenchState.constraintMetadata = registry.constraints;
    workbenchState.recoveryColumns = precheckInputs.recovery_columns;
    workbenchState.passengerCapacityProfile = precheckInputs.passenger_capacity_profile;
    workbenchState.capacityProfileSummary = registry.capacity_profile_summary;
    workbenchState.modelProfile = registry.model_profile;
    renderShell();
    renderDataView();
  } catch (error) {
    showClientError(`Workbench initialization failed: ${error.message}`);
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
viewButtons.costs.addEventListener("click", openCosts);
viewButtons.constraints.addEventListener("click", openConstraints);
document.querySelector("#load-example").addEventListener("click", setExample);
document.querySelector("#reset-scenario").addEventListener("click", () => {
  workbenchState.scenario = clone(workbenchState.scenarioBaseline);
  workbenchState.scenarioValidation = null;
  workbenchState.constraintPrecheck = null;
  if (activeView === "data") renderDataView();
  else if (activeView === "visualization") openVisualization();
  else if (activeView === "constraints") openConstraints();
  updateSummary();
});
document.querySelector("#reset-workbench").addEventListener("click", () => {
  workbenchState.scenario = clone(workbenchState.scenarioBaseline);
  workbenchState.scenarioValidation = null;
  workbenchState.costOverrides = {};
  workbenchState.costEffective = clone(workbenchState.costBaseline);
  workbenchState.constraintPrecheck = null;
  setCostStatus("baseline", "Scenario and cost overrides restored to their loaded baselines.");
  if (activeView === "data") renderDataView();
  else if (activeView === "visualization") openVisualization();
  else if (activeView === "constraints") openConstraints();
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
  if (index < 0) return showClientError("Select a row to duplicate.");
  workbenchState.scenario[activeSection].splice(index + 1, 0, clone(workbenchState.scenario[activeSection][index]));
  markScenarioChanged();
  renderDataView();
});
document.querySelector("#delete-row").addEventListener("click", () => {
  const index = selectedRowIndex();
  if (index < 0) return showClientError("Select a row to delete.");
  workbenchState.scenario[activeSection].splice(index, 1);
  markScenarioChanged();
  renderDataView();
});
document.querySelector("#validate").addEventListener("click", async () => {
  if (activeView === "visualization") return openVisualization();
  if (activeView === "constraints") return runPrecheck();
  if (activeView === "costs") return document.querySelector("#validate-costs").click();
  try {
    const result = await validateScenario(workbenchState.scenario);
    workbenchState.scenarioValidation = result.valid ? "valid" : "invalid";
    showValidation(result);
    updateSummary();
  } catch (error) {
    showClientError(error.message);
  }
});
document.querySelector("#validate-costs").addEventListener("click", async () => {
  try {
    const result = await validateCostOverrides({
      base_cost_profile_id: workbenchState.costBaseline.cost_profile_id,
      overrides: workbenchState.costOverrides,
    });
    workbenchState.costEffective = result.effective_profile;
    setCostStatus("valid", `Validated ${Object.keys(result.overrides).length} override(s); canonical metadata is unchanged.`);
    renderCostView();
  } catch (error) {
    setCostStatus("invalid", error.message);
  }
});
document.querySelector("#reset-cost-overrides").addEventListener("click", () => {
  workbenchState.costOverrides = {};
  workbenchState.costEffective = clone(workbenchState.costBaseline);
  setCostStatus("baseline", "Overrides cleared; effective values equal the canonical baseline.");
  renderCostView();
});
document.querySelector("#run-precheck").addEventListener("click", runPrecheck);
document.querySelector("#export-scenario").addEventListener("click", () => {
  downloadJson(workbenchState.scenario, `${workbenchState.scenario.scenario_id || "scenario"}.json`);
});
document.querySelector("#export-workbench").addEventListener("click", () => {
  const config = buildWorkbenchConfig(
    workbenchState.scenario,
    workbenchState.costBaseline,
    workbenchState.costOverrides,
    workbenchState.capacityProfileSummary,
    workbenchState.modelProfile,
  );
  downloadJson(config, `${workbenchState.scenario.scenario_id || "scenario"}_workbench.json`);
});

const fileInput = document.querySelector("#file-input");
document.querySelector("#import-json").addEventListener("click", () => fileInput.click());
fileInput.addEventListener("change", async () => {
  const [file] = fileInput.files;
  if (!file) return;
  try {
    const imported = JSON.parse(await file.text());
    if ("scenario" in imported || "cost_overrides" in imported) {
      throw new Error("Select a Scenario JSON file; Workbench Config import is not enabled.");
    }
    const result = await validateScenario(imported);
    if (!result.valid) {
      showValidation(result);
      if (activeView === "visualization") renderVisualizationBlocked(result, showDataView);
      return;
    }
    workbenchState.scenario = result.normalized_data;
    workbenchState.scenarioBaseline = clone(result.normalized_data);
    if (workbenchState.recoveryColumns?.scenario_id !== result.normalized_data.scenario_id) {
      workbenchState.recoveryColumns = null;
      workbenchState.passengerCapacityProfile = null;
    }
    workbenchState.scenarioValidation = "valid";
    workbenchState.constraintPrecheck = null;
    activeSection = "scenario";
    showValidation(result);
    showDataView();
  } catch (error) {
    showClientError(`Import failed: ${error.message}`);
  } finally {
    fileInput.value = "";
  }
});

renderShell();
initializeWorkbench();
