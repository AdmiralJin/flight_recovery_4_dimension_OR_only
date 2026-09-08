import { loadExample, validateScenario } from "./api.js";
import { showClientError, showValidation } from "./results.js";
import { blankRow, renderEditor, sections } from "./tables.js";

let state = null;
let baseline = null;
let activeSection = "scenario";

const clone = (value) => structuredClone(value);
const editor = document.querySelector("#editor");
const tabs = document.querySelector("#tabs");
const actions = document.querySelector("#table-actions");

function selectedRowIndex() {
  const selected = document.querySelector('input[name="selected-row"]:checked');
  return selected ? Number(selected.value) : -1;
}

function updateSummary() {
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
      render();
    });
    tabs.append(button);
  }
}

function render() {
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

async function setExample() {
  try {
    state = await loadExample();
    baseline = clone(state);
    activeSection = "scenario";
    render();
  } catch (error) {
    showClientError(error.message);
  }
}

document.querySelector("#load-example").addEventListener("click", setExample);
document.querySelector("#reset-all").addEventListener("click", () => {
  state = clone(baseline);
  render();
});
document.querySelector("#reset-section").addEventListener("click", () => {
  state[activeSection] = clone(baseline[activeSection]);
  render();
});
document.querySelector("#add-row").addEventListener("click", () => {
  state[activeSection].push(blankRow(activeSection));
  render();
});
document.querySelector("#duplicate-row").addEventListener("click", () => {
  const index = selectedRowIndex();
  if (index < 0) return showClientError("Select a row to duplicate.");
  state[activeSection].splice(index + 1, 0, clone(state[activeSection][index]));
  render();
});
document.querySelector("#delete-row").addEventListener("click", () => {
  const index = selectedRowIndex();
  if (index < 0) return showClientError("Select a row to delete.");
  state[activeSection].splice(index, 1);
  render();
});
document.querySelector("#validate").addEventListener("click", async () => {
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
      return;
    }
    state = result.normalized_data;
    baseline = clone(state);
    activeSection = "scenario";
    render();
    showValidation(result);
  } catch (error) {
    showClientError(`Import failed: ${error.message}`);
  } finally {
    fileInput.value = "";
  }
});

setExample();

