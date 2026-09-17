import {
  loadCanonicalCosts,
  loadHealth,
  loadSolveExampleBundle,
  loadSolveExamples,
  loadScenarioExample,
  checkSolveReadiness,
  solveRecovery,
  loadConstraintRegistry,
  runConstraintPrecheck,
  validateCostOverrides,
  validateScenario,
} from "./api.js";
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
import {
  acceptSolveResult,
  beginSolve,
  buildCurrentSolveBundle,
  finishSolve,
  restoreCaseBaseline,
  snapshotCaseBaseline,
} from "./workbench-state.js";

const clone = (value) => structuredClone(value);

const workbenchState = {
  caseId: null,
  source: null,
  loadedAt: null,
  baseline: null,
  revision: 0,
  dirty: false,
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
  solveBundle: null,
  solveReadiness: null,
  recoveredResult: null,
  solveError: null,
  solving: false,
  solveStartedAt: null,
  solveTimer: null,
  recoveredResultRevision: null,
  recoverySortDelay: false,
  apiHealth: null,
};

let activeSection = "scenario";
let activeView = "data";
let visualizationRequestId = 0;
let precheckRequestId = 0;
let solveReadinessRequestId = 0;

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
  return workbenchState.dirty || (workbenchState.scenarioBaseline
    && JSON.stringify(workbenchState.scenario) !== JSON.stringify(workbenchState.scenarioBaseline));
}

function showGlobalNotice(message, kind = "info") {
  const region = document.querySelector("#global-toast-region");
  const toast = document.createElement("div");
  toast.className = `global-toast ${kind}`;
  toast.textContent = message;
  region.append(toast);
  window.setTimeout(() => toast.remove(), 6000);
}

function missingInputLabel(value) {
  return String(value || "").replaceAll("_", " ");
}

function currentCapacitySummary() {
  const profile = workbenchState.passengerCapacityProfile;
  if (!profile) return null;
  return {
    capacity_profile_id: profile.capacity_profile_id || "current case capacity",
    display_label: "CURRENT CASE / PASSENGER CAPACITY",
    source: "solve bundle",
    units: "seats",
    seat_capacity_by_option_id: profile.seat_capacity_by_option_id || {},
    notes: ["This summary is bound to the currently loaded case; it does not fall back to the benchmark."],
  };
}

function captureBaseline() {
  workbenchState.baseline = snapshotCaseBaseline(workbenchState);
  workbenchState.scenarioBaseline = clone(workbenchState.scenario);
}

function invalidateRecovery() {
  workbenchState.recoveredResult = null;
  workbenchState.recoveredResultRevision = null;
  workbenchState.solveError = null;
  document.querySelector("#export-recovered-result").disabled = true;
}

function bumpRevision() {
  workbenchState.revision += 1;
  workbenchState.dirty = true;
  invalidateRecovery();
}

function setSolvingState(solving) {
  workbenchState.solving = solving;
  const mutableSelectors = [
    "#load-example", "#reload-example", "#import-json", "#reset-scenario", "#reset-workbench",
    "#reset-section", "#add-row", "#duplicate-row", "#delete-row", "#reset-cost-overrides",
    "#validate-costs", "#run-precheck", "#example-selector",
  ];
  for (const selector of mutableSelectors) {
    const element = document.querySelector(selector);
    if (element) element.disabled = solving;
  }
  document.querySelectorAll("#editor input, #editor textarea, #editor select, #costs-container input").forEach((element) => {
    element.disabled = solving;
  });
  if (solving) {
    workbenchState.solveStartedAt = Date.now();
    workbenchState.solveTimer = window.setInterval(() => {
      updateSolveButton();
      updateSummary();
    }, 1000);
  } else {
    window.clearInterval(workbenchState.solveTimer);
    workbenchState.solveTimer = null;
    workbenchState.solveStartedAt = null;
  }
  updateSolveButton();
  updateSummary();
}

function elapsedLabel() {
  const elapsed = workbenchState.solveStartedAt ? Math.floor((Date.now() - workbenchState.solveStartedAt) / 1000) : 0;
  return `${String(Math.floor(elapsed / 60)).padStart(2, "0")}:${String(elapsed % 60).padStart(2, "0")}`;
}

function updateSummary() {
  const state = workbenchState.scenario;
  if (!state) return;
  const total = ["airports", "flights", "aircraft", "crew", "passengers", "airport_intervals", "disruptions"]
    .reduce((sum, key) => sum + state[key].length, 0);
  const scenarioStatus = workbenchState.scenarioValidation === "valid" ? "VALID" : "UNVALIDATED";
  document.querySelector("#record-summary").textContent = `${workbenchState.caseId || state.scenario_id} · ${scenarioIsModified() ? "MODIFIED" : scenarioStatus} · rev ${workbenchState.revision}`;
  const readiness = workbenchState.solveReadiness;
  const readinessReasons = readiness ? [...(readiness.missing_inputs || []), ...(readiness.invalid_profiles || [])] : [];
  const readinessText = readiness?.solve_ready ? "READY" : `NOT READY${readinessReasons.length ? `: ${readinessReasons.map(missingInputLabel).join(", ")}` : ""}`;
  document.querySelector("#solve-readiness-summary").textContent = readinessText;
  document.querySelector("#solver-summary").textContent = workbenchState.solving ? `SOLVING ${elapsedLabel()}` : "IDLE";
  const resultText = workbenchState.recoveredResult
    ? (workbenchState.recoveredResultRevision === workbenchState.revision ? `SOLVED · ${workbenchState.recoveredResult.status}` : "STALE RESULT")
    : workbenchState.solveError ? "ERROR" : "NONE";
  document.querySelector("#result-summary").textContent = resultText;
  const health = workbenchState.apiHealth;
  document.querySelector("#api-health-summary").textContent = health
    ? `${health.status === "ok" ? "ONLINE" : "DEGRADED"} · ${health.solver_enabled ? "SOLVER ENABLED" : "SOLVER DISABLED"}`
    : "UNAVAILABLE";
}

function renderCaseMetadata() {
  const container = document.querySelector("#case-metadata");
  if (!container || !workbenchState.scenario) return;
  const schema = workbenchState.solveBundle?.schema_version || "Scenario only";
  const items = [
    ["Case", workbenchState.caseId],
    ["Source", workbenchState.source],
    ["Scenario", workbenchState.scenario.scenario_id],
    ["Solve Bundle", schema],
    ["Revision", workbenchState.revision],
    ["Loaded", workbenchState.loadedAt ? new Date(workbenchState.loadedAt).toLocaleString() : "—"],
  ];
  container.replaceChildren(...items.map(([label, value]) => {
    const item = document.createElement("span");
    const strong = document.createElement("strong");
    strong.textContent = `${label}: `;
    item.append(strong, document.createTextNode(String(value ?? "—")));
    return item;
  }));
}

function markScenarioChanged() {
  workbenchState.scenarioValidation = null;
  workbenchState.constraintPrecheck = null;
  bumpRevision();
  refreshSolveReadiness();
  updateSummary();
  renderTabs();
}

function currentSolveBundle() {
  return buildCurrentSolveBundle(workbenchState);
}

function updateSolveButton() {
  const button = document.querySelector("#solve-recovery");
  const ready = workbenchState.solveReadiness?.solve_ready && !workbenchState.solving;
  button.disabled = !ready;
  button.textContent = workbenchState.solving ? `Solving ${elapsedLabel()}` : "Solve";
  const status = document.querySelector("#solve-status");
  if (!status) return;
  if (workbenchState.solving) status.textContent = `Solving exact recovery · ${elapsedLabel()}${Date.now() - workbenchState.solveStartedAt > 30000 ? " · taking longer than the benchmark baseline" : ""}`;
  else if (workbenchState.solveError) status.textContent = `Solve failed: ${workbenchState.solveError}`;
  else if (!workbenchState.solveReadiness?.solve_ready) {
    const reasons = workbenchState.solveReadiness
      ? [...(workbenchState.solveReadiness.missing_inputs || []), ...(workbenchState.solveReadiness.invalid_profiles || [])]
      : ["Load a complete Solve Bundle"];
    status.textContent = `Solve unavailable: ${reasons.map(missingInputLabel).join(", ")}`;
    button.title = status.textContent;
  } else if (workbenchState.recoveredResult) status.textContent = `Solver status: ${workbenchState.recoveredResult.status}`;
  else status.textContent = "Ready to solve · input readiness is not optimization feasibility.";
  if (ready) button.removeAttribute("title");
}

async function refreshSolveReadiness() {
  const requestId = ++solveReadinessRequestId;
  const bundle = currentSolveBundle();
  if (!bundle) {
    workbenchState.solveReadiness = {
      solve_ready: false,
      missing_inputs: [
        "missing_flight_options",
        ...(workbenchState.scenario?.passengers?.length ? ["missing_passenger_itineraries"] : []),
        "missing_capacity_profile",
        "missing_algorithm_profiles",
      ],
      invalid_profiles: [],
      warnings: [],
    };
    updateSolveButton();
    return;
  }
  try {
    const readiness = await checkSolveReadiness(bundle);
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
  renderRecovery(
    document.querySelector("#recovery-container"), workbenchState.scenario,
    workbenchState.recoveredResult,
    document.querySelector("#recovery-mode").value,
    workbenchState.recoverySortDelay,
  );
  updateSolveButton();
}

async function runSolve() {
  const request = beginSolve(workbenchState);
  if (!request) return;
  // Lock before the asynchronous readiness check so a double click cannot create two requests.
  setSolvingState(true);
  try {
    const readiness = await checkSolveReadiness(request.bundle);
    workbenchState.solveReadiness = readiness;
    if (!readiness.solve_ready) {
      const reasons = [...(readiness.missing_inputs || []), ...(readiness.invalid_profiles || [])];
      showGlobalNotice(`Solve unavailable: ${reasons.map(missingInputLabel).join(", ")}`, "warning");
      return openRecovery();
    }
    const result = await solveRecovery(request.bundle);
    if (!acceptSolveResult(workbenchState, request, result)) {
      showGlobalNotice("Solve result discarded because the workbench input changed.", "warning");
      return;
    }
    document.querySelector("#export-recovered-result").disabled = false;
    showGlobalNotice(`Solve completed: ${result.status}${result.objective?.total !== undefined ? ` · objective ${result.objective.total}` : ""}`, "success");
    openRecovery();
  } catch (error) {
    workbenchState.recoveredResult = null;
    workbenchState.solveError = error.message;
    openRecovery();
    showClientError(error.message);
    showGlobalNotice(error.message, "error");
  } finally {
    finishSolve(workbenchState);
    setSolvingState(false);
  }
}

function applyScenario(scenario, caseId = scenario.scenario_id, source = "import") {
  workbenchState.caseId = caseId;
  workbenchState.source = source;
  workbenchState.loadedAt = new Date().toISOString();
  workbenchState.scenario = clone(scenario);
  workbenchState.solveBundle = null;
  workbenchState.recoveryColumns = null;
  workbenchState.passengerCapacityProfile = null;
  workbenchState.costOverrides = {};
  workbenchState.costEffective = buildEffectiveCostProfile(workbenchState.costBaseline, {});
  workbenchState.scenarioValidation = null;
  workbenchState.constraintPrecheck = null;
  workbenchState.solveReadiness = null;
  workbenchState.revision += 1;
  workbenchState.dirty = false;
  invalidateRecovery();
  captureBaseline();
}

function applySolveBundle(bundle, caseId = bundle.scenario?.scenario_id, source = "import") {
  workbenchState.caseId = caseId;
  workbenchState.source = source;
  workbenchState.loadedAt = new Date().toISOString();
  workbenchState.solveBundle = clone(bundle);
  workbenchState.scenario = clone(bundle.scenario);
  workbenchState.recoveryColumns = clone(bundle.recovery_columns);
  workbenchState.passengerCapacityProfile = clone(bundle.capacity_profile);
  workbenchState.costOverrides = clone(bundle.cost_overrides || {});
  workbenchState.costEffective = buildEffectiveCostProfile(workbenchState.costBaseline, workbenchState.costOverrides);
  workbenchState.scenarioValidation = null;
  workbenchState.constraintPrecheck = null;
  workbenchState.solveReadiness = null;
  workbenchState.revision += 1;
  workbenchState.dirty = false;
  invalidateRecovery();
  captureBaseline();
}

function resetToBaseline() {
  if (!restoreCaseBaseline(workbenchState)) return;
  workbenchState.costEffective = buildEffectiveCostProfile(workbenchState.costBaseline, workbenchState.costOverrides);
  workbenchState.scenarioValidation = null;
  workbenchState.constraintPrecheck = null;
  workbenchState.solveReadiness = null;
  invalidateRecovery();
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
  const exportBundle = document.querySelector("#export-solve-bundle");
  exportBundle.disabled = !workbenchState.solveBundle;
  exportBundle.title = workbenchState.solveBundle ? "" : "No Solve Bundle is loaded for this Scenario-only case.";
  renderCaseMetadata();
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
  if (workbenchState.solving) {
    editor.querySelectorAll("input, textarea, select").forEach((element) => { element.disabled = true; });
  }
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
    renderVisualization(result.normalized_data, openRecovery);
  } catch (error) {
    if (requestId !== visualizationRequestId || activeView !== "visualization") return;
    const result = { valid: false, errors: [{ location: "$", message: error.message }] };
    showClientError(error.message);
    showGlobalNotice(error.message, "error");
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
  if (workbenchState.solving) return;
  try {
    const value = parseCostOverride(rawValue);
    if (value === null) delete workbenchState.costOverrides[key];
    else workbenchState.costOverrides[key] = value;
    workbenchState.costEffective = buildEffectiveCostProfile(
      workbenchState.costBaseline,
      workbenchState.costOverrides,
    );
    bumpRevision();
    refreshSolveReadiness();
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
  if (workbenchState.solving) {
    document.querySelectorAll("#costs-container input").forEach((element) => { element.disabled = true; });
  }
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
  const capacity = currentCapacitySummary();
  const columns = workbenchState.recoveryColumns;
  document.querySelector("#recovery-columns-summary").textContent = columns
    ? `Current case Recovery Columns: ${(columns.flight_options || []).length} flight options, ${(columns.passenger_itineraries || []).length} passenger itineraries, ${(columns.aircraft_strings || []).length} aircraft strings, ${(columns.crew_pairings || []).length} crew pairings.`
    : "No recovery columns loaded. This Scenario is not solve-ready.";
  const capacityContainer = document.querySelector("#capacity-profile-summary");
  if (capacity) renderCapacityProfileSummary(capacityContainer, capacity);
  else capacityContainer.textContent = "No passenger capacity profile loaded. This Scenario is not solve-ready.";
  renderConstraintInspector(
    document.querySelector("#constraints-container"),
    workbenchState.constraintMetadata,
    workbenchState.constraintPrecheck,
    showDataView,
  );
  setPrecheckStatus(workbenchState.constraintPrecheck);
}

async function runPrecheck() {
  if (workbenchState.solving) return;
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
    showGlobalNotice(error.message, "error");
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
  if (workbenchState.solving) return;
  try {
    const selector = document.querySelector("#example-selector");
    const option = selector.selectedOptions[0];
    const caseId = selector.value;
    if (option?.dataset.type === "solve_bundle") {
      applySolveBundle(await loadSolveExampleBundle(caseId), caseId, "example");
    } else {
      applyScenario(await loadScenarioExample(caseId), caseId, "example");
    }
    await refreshSolveReadiness();
    activeSection = "scenario";
    if (activeView === "visualization") await openVisualization();
    else if (activeView === "constraints") await openConstraints();
    else {
      renderShell();
      if (activeView === "data") renderDataView();
      else if (activeView === "recovery") openRecovery();
      else renderCostView();
    }
  } catch (error) {
    showClientError(error.message);
    showGlobalNotice(error.message, "error");
  }
}

async function initializeWorkbench() {
  try {
    const [costs, registry, examples, health] = await Promise.all([
      loadCanonicalCosts(),
      loadConstraintRegistry(),
      loadSolveExamples(),
      loadHealth(),
    ]);
    workbenchState.costBaseline = costs;
    workbenchState.costEffective = clone(costs);
    workbenchState.constraintMetadata = registry.constraints;
    workbenchState.capacityProfileSummary = registry.capacity_profile_summary;
    workbenchState.modelProfile = registry.model_profile;
    workbenchState.apiHealth = health;
    const selector = document.querySelector("#example-selector");
    selector.replaceChildren();
    for (const example of examples) {
      const option = document.createElement("option");
      option.value = example.case_id;
      option.dataset.type = example.type;
      option.textContent = `${example.label}${example.solve_ready ? "" : " — Scenario only"}`;
      selector.append(option);
    }
    const requestedCase = new URLSearchParams(window.location.search).get("case");
    if (requestedCase && [...selector.options].some((item) => item.value === requestedCase)) selector.value = requestedCase;
    await setExample();
    renderShell();
    renderDataView();
  } catch (error) {
    showClientError(`Workbench initialization failed: ${error.message}`);
    showGlobalNotice(`Workbench initialization failed: ${error.message}`, "error");
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
document.querySelector("#load-example").addEventListener("click", setExample);
document.querySelector("#reload-example").addEventListener("click", setExample);
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
document.querySelector("#reset-scenario").addEventListener("click", () => {
  if (workbenchState.solving) return;
  workbenchState.scenario = clone(workbenchState.scenarioBaseline);
  workbenchState.scenarioValidation = null;
  workbenchState.constraintPrecheck = null;
  bumpRevision();
  refreshSolveReadiness();
  if (activeView === "data") renderDataView();
  else if (activeView === "visualization") openVisualization();
  else if (activeView === "constraints") openConstraints();
  else if (activeView === "recovery") openRecovery();
  updateSummary();
});
document.querySelector("#reset-workbench").addEventListener("click", () => {
  if (workbenchState.solving) return;
  resetToBaseline();
  refreshSolveReadiness();
  setCostStatus(Object.keys(workbenchState.costOverrides).length ? "modified" : "baseline", "Scenario and cost overrides restored to the current case baseline.");
  if (activeView === "data") renderDataView();
  else if (activeView === "visualization") openVisualization();
  else if (activeView === "constraints") openConstraints();
  else if (activeView === "recovery") openRecovery();
  else renderCostView();
});
document.querySelector("#reset-section").addEventListener("click", () => {
  if (workbenchState.solving) return;
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
  if (workbenchState.solving) return;
  workbenchState.scenario[activeSection].push(blankRow(activeSection));
  markScenarioChanged();
  renderDataView();
});
document.querySelector("#duplicate-row").addEventListener("click", () => {
  if (workbenchState.solving) return;
  const index = selectedRowIndex();
  if (index < 0) return showClientError("Select a row to duplicate.");
  workbenchState.scenario[activeSection].splice(index + 1, 0, clone(workbenchState.scenario[activeSection][index]));
  markScenarioChanged();
  renderDataView();
});
document.querySelector("#delete-row").addEventListener("click", () => {
  if (workbenchState.solving) return;
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
  if (activeView === "recovery") {
    await refreshSolveReadiness();
    const readiness = workbenchState.solveReadiness;
    const currentResult = workbenchState.recoveredResultRevision === workbenchState.revision;
    showGlobalNotice(
      readiness?.solve_ready
        ? `Solve Bundle is ready. Recovered Result: ${currentResult ? "current" : "none or stale"}.`
        : `Solve Bundle is not ready: ${[...(readiness?.missing_inputs || []), ...(readiness?.invalid_profiles || [])].map(missingInputLabel).join(", ")}`,
      readiness?.solve_ready ? "success" : "warning",
    );
    return;
  }
  try {
    const result = await validateScenario(workbenchState.scenario);
    workbenchState.scenarioValidation = result.valid ? "valid" : "invalid";
    showValidation(result);
    updateSummary();
    showGlobalNotice(result.valid ? "Scenario validation passed." : `Scenario validation found ${result.errors?.length || 0} issue(s).`, result.valid ? "success" : "warning");
  } catch (error) {
    showClientError(error.message);
    showGlobalNotice(error.message, "error");
  }
});
document.querySelector("#validate-costs").addEventListener("click", async () => {
  try {
    const result = await validateCostOverrides({
      base_cost_profile_id: workbenchState.costBaseline.cost_profile_id,
      overrides: workbenchState.costOverrides,
    });
    workbenchState.costEffective = result.effective_profile;
    invalidateRecovery();
    refreshSolveReadiness();
    setCostStatus("valid", `Validated ${Object.keys(result.overrides).length} override(s); canonical metadata is unchanged.`);
    renderCostView();
    showGlobalNotice("Cost configuration validation passed.", "success");
  } catch (error) {
    setCostStatus("invalid", error.message);
    showGlobalNotice(error.message, "error");
  }
});
document.querySelector("#reset-cost-overrides").addEventListener("click", () => {
  if (workbenchState.solving) return;
  workbenchState.costOverrides = clone(workbenchState.baseline?.costOverrides || {});
  workbenchState.costEffective = buildEffectiveCostProfile(workbenchState.costBaseline, workbenchState.costOverrides);
  bumpRevision();
  refreshSolveReadiness();
  setCostStatus(Object.keys(workbenchState.costOverrides).length ? "modified" : "baseline", "Overrides restored to the current case baseline.");
  renderCostView();
});
document.querySelector("#run-precheck").addEventListener("click", runPrecheck);
document.querySelector("#export-scenario").addEventListener("click", () => {
  downloadJson(workbenchState.scenario, `${workbenchState.scenario.scenario_id || "scenario"}.json`);
});
document.querySelector("#export-solve-bundle").addEventListener("click", () => {
  const bundle = currentSolveBundle();
  if (bundle) downloadJson(bundle, `${workbenchState.scenario.scenario_id || "scenario"}_solve_bundle.json`);
});
document.querySelector("#export-workbench").addEventListener("click", () => {
  const snapshot = {
    snapshot_type: "workbench_snapshot_v1",
    case_id: workbenchState.caseId,
    source: workbenchState.source,
    solve_bundle: currentSolveBundle(),
    scenario: clone(workbenchState.scenario),
    cost_overrides: clone(workbenchState.costOverrides),
  };
  downloadJson(snapshot, `${workbenchState.scenario.scenario_id || "scenario"}_workbench_snapshot.json`);
});

const fileInput = document.querySelector("#file-input");
document.querySelector("#import-json").addEventListener("click", () => fileInput.click());
fileInput.addEventListener("change", async () => {
  const [file] = fileInput.files;
  if (!file) return;
  try {
    const imported = JSON.parse(await file.text());
    if (workbenchState.solving) return;
    const snapshot = imported.snapshot_type === "workbench_snapshot_v1";
    const candidate = snapshot ? imported.solve_bundle : imported;
    const isSolveBundle = candidate?.schema_version === "1.0.0" && "recovery_columns" in candidate;
    if (!isSolveBundle && ("scenario" in imported || "cost_overrides" in imported) && !snapshot) throw new Error("Detected an incomplete workbench config. Import Scenario, Solve Bundle, or Workbench Snapshot.");
    if (isSolveBundle) {
      const readiness = await checkSolveReadiness(candidate);
      if (!readiness.solve_ready) throw new Error(`Solve Bundle is not ready: ${[...readiness.missing_inputs, ...readiness.invalid_profiles].join(", ")}`);
    }
    const scenario = isSolveBundle ? candidate.scenario : snapshot ? imported.scenario : imported;
    if (!scenario) throw new Error("Workbench Snapshot is missing Scenario data.");
    const result = await validateScenario(scenario);
    if (!result.valid) {
      showValidation(result);
      if (activeView === "visualization") renderVisualizationBlocked(result, showDataView);
      return;
    }
    if (isSolveBundle) {
      candidate.scenario = result.normalized_data;
      applySolveBundle(candidate, snapshot ? imported.case_id : result.normalized_data.scenario_id, "import");
    } else {
      applyScenario(result.normalized_data, snapshot ? imported.case_id : result.normalized_data.scenario_id, "import");
      if (snapshot) {
        workbenchState.costOverrides = clone(imported.cost_overrides || {});
        workbenchState.costEffective = buildEffectiveCostProfile(workbenchState.costBaseline, workbenchState.costOverrides);
        captureBaseline();
      }
    }
    await refreshSolveReadiness();
    workbenchState.scenarioValidation = "valid";
    activeSection = "scenario";
    showValidation(result);
    showGlobalNotice(`Imported ${isSolveBundle ? "Solve Bundle" : "Scenario"}: ${workbenchState.caseId}`, "success");
    showDataView();
  } catch (error) {
    showClientError(`Import failed: ${error.message}`);
    showGlobalNotice(`Import failed: ${error.message}`, "error");
  } finally {
    fileInput.value = "";
  }
});

renderShell();
initializeWorkbench();
