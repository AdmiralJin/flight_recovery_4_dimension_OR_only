import { loadExample, validateScenario } from "./api.js";
import { showClientError, showValidation } from "./results.js";
import { blankRow, renderEditor, sections } from "./tables.js";
import {
  renderVisualization,
  renderVisualizationBlocked,
  renderVisualizationLoading,
} from "./visualization.js";

let state = null;
let baseline = null;
let activeSection = "scenario";
let activeView = "data";
let visualizationRequestId = 0;

const clone = (value) => structuredClone(value);
const editor = document.querySelector("#editor");
const tabs = document.querySelector("#tabs");
const actions = document.querySelector("#table-actions");
const dataView = document.querySelector("#data-view");
const visualizationView = document.querySelector("#visualization-view");

function selectedRowIndex() {
  const selected = document.querySelector('input[name="selected-row"]:checked');
  return selected ? Number(selected.value) : -1;
}

function updateSummary() {
  if (!state) return;
  const total = ["airports", "flights", "aircraft", "crew", "passengers", "airport_intervals", "disruptions"]
    .reduce((sum, key) => sum + state[key].length, 0);
  document.querySelector("#record-summary").textContent = `${state.scenario_id} · ${total} records`;
}

function renderTabs() {
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
  const isData = activeView === "data";
  dataView.hidden = !isData;
  visualizationView.hidden = isData;
  document.querySelector("#show-data-view").setAttribute("aria-pressed", String(isData));
  document.querySelector("#show-visualization-view").setAttribute("aria-pressed", String(!isData));
}

function renderDataView() {
  if (!state) return;
  const meta = sections.find((section) => section.key === activeSection);
  document.querySelector("#section-kicker").textContent = meta.label.toUpperCase();
  document.querySelector("#section-title").textContent = meta.title;
  actions.hidden = activeSection === "scenario";
  renderTabs();
  renderEditor(editor, activeSection, state, () => {
    updateSummary();
    renderTabs();
  });
  updateSummary();
}

function showDataView() {
  visualizationRequestId += 1;
  activeView = "data";
  renderShell();
  renderDataView();
}

async function openVisualization() {
  if (!state) return;
  activeView = "visualization";
  renderShell();
  renderVisualizationLoading();
  const requestId = ++visualizationRequestId;
  try {
    const result = await validateScenario(state);
    if (requestId !== visualizationRequestId || activeView !== "visualization") return;
    showValidation(result);
    if (!result.valid) {
      renderVisualizationBlocked(result, showDataView);
      return;
    }
    renderVisualization(result.normalized_data);
  } catch (error) {
    if (requestId !== visualizationRequestId || activeView !== "visualization") return;
    const result = {
      valid: false,
      errors: [{ location: "$", message: error.message }],
    };
    showClientError(error.message);
    renderVisualizationBlocked(result, showDataView);
  }
}

async function refreshCurrentView() {
  renderShell();
  updateSummary();
  if (activeView === "visualization") await openVisualization();
  else renderDataView();
}

async function setExample() {
  try {
    state = await loadExample();
    baseline = clone(state);
    activeSection = "scenario";
    await refreshCurrentView();
  } catch (error) {
    showClientError(error.message);
  }
}

document.querySelector("#show-data-view").addEventListener("click", showDataView);
document.querySelector("#show-visualization-view").addEventListener("click", openVisualization);
document.querySelector("#load-example").addEventListener("click", setExample);
document.querySelector("#reset-all").addEventListener("click", async () => {
  state = clone(baseline);
  await refreshCurrentView();
});
document.querySelector("#reset-section").addEventListener("click", () => {
  state[activeSection] = clone(baseline[activeSection]);
  renderDataView();
});
document.querySelector("#add-row").addEventListener("click", () => {
  state[activeSection].push(blankRow(activeSection));
  renderDataView();
});
document.querySelector("#duplicate-row").addEventListener("click", () => {
  const index = selectedRowIndex();
  if (index < 0) return showClientError("Select a row to duplicate.");
  state[activeSection].splice(index + 1, 0, clone(state[activeSection][index]));
  renderDataView();
});
document.querySelector("#delete-row").addEventListener("click", () => {
  const index = selectedRowIndex();
  if (index < 0) return showClientError("Select a row to delete.");
  state[activeSection].splice(index, 1);
  renderDataView();
});
document.querySelector("#validate").addEventListener("click", async () => {
  if (activeView === "visualization") {
    await openVisualization();
    return;
  }
  try {
    showValidation(await validateScenario(state));
  } catch (error) {
    showClientError(error.message);
  }
});
document.querySelector("#export-json").addEventListener("click", () => {
  const blob = new Blob([`${JSON.stringify(state, null, 2)}\n`], { type: "application/json" });
  const link = document.createElement("a");
  link.href = URL.createObjectURL(blob);
  link.download = `${state.scenario_id || "scenario"}.json`;
  link.click();
  URL.revokeObjectURL(link.href);
});

const fileInput = document.querySelector("#file-input");
document.querySelector("#import-json").addEventListener("click", () => fileInput.click());
fileInput.addEventListener("change", async () => {
  const [file] = fileInput.files;
  if (!file) return;
  try {
    const imported = JSON.parse(await file.text());
    const result = await validateScenario(imported);
    if (!result.valid) {
      showValidation(result);
      if (activeView === "visualization") renderVisualizationBlocked(result, showDataView);
      return;
    }
    state = result.normalized_data;
    baseline = clone(state);
    activeSection = "scenario";
    showValidation(result);
    await refreshCurrentView();
  } catch (error) {
    showClientError(`Import failed: ${error.message}`);
  } finally {
    fileInput.value = "";
  }
});

renderShell();
setExample();

