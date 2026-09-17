function showToast(message, kind = "info") {
  const region = document.querySelector("#global-toast-region");
  if (!region) return;
  const toast = document.createElement("div");
  toast.className = `global-toast ${kind}`;
  toast.textContent = message;
  region.append(toast);
  window.setTimeout(() => toast.remove(), 6000);
}

function updateGuidance() {
  const summary = document.querySelector("#solve-readiness-summary");
  const guidance = document.querySelector("#solve-guidance");
  if (!summary || !guidance) return;
  const text = summary.textContent.trim();
  guidance.classList.remove("is-ready", "is-warning");
  if (text === "READY") {
    guidance.classList.add("is-ready");
    guidance.textContent = "Solve input is READY. You may Validate / inspect the case, then click Solve. Inputs will be locked while solving.";
    return;
  }
  if (text.startsWith("NOT READY")) {
    guidance.classList.add("is-warning");
    guidance.textContent = `${text}. This case can still be inspected and validated. To solve, load/import a complete Solve Bundle or use a Scenario with compatible repository Columns and Capacity.`;
    return;
  }
  guidance.textContent = "Checking whether the current case has all required solve inputs…";
}

const readinessSummary = document.querySelector("#solve-readiness-summary");
if (readinessSummary) {
  new MutationObserver(updateGuidance).observe(readinessSummary, {
    childList: true,
    characterData: true,
    subtree: true,
  });
  updateGuidance();
}

const helpDialog = document.querySelector("#workflow-help");
document.querySelector("#workflow-help-open")?.addEventListener("click", () => {
  if (helpDialog?.showModal) helpDialog.showModal();
});

let replayingImport = false;

function replayImport(input) {
  replayingImport = true;
  input.dispatchEvent(new Event("change", { bubbles: true }));
  replayingImport = false;
}

async function hydrateScenarioImport(input, file, imported) {
  const response = await fetch("/api/solve/hydrate", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(imported),
  });
  if (!response.ok) {
    replayImport(input);
    return;
  }

  const bundle = await response.json();
  try {
    const transfer = new DataTransfer();
    const hydrated = new File(
      [`${JSON.stringify(bundle, null, 2)}\n`],
      file.name,
      { type: "application/json", lastModified: Date.now() },
    );
    transfer.items.add(hydrated);
    input.files = transfer.files;
    showToast(
      `Matched ${imported.scenario_id} to repository solve fixtures. Importing as a complete Solve Bundle.`,
      "success",
    );
    replayImport(input);
  } catch (error) {
    showToast(`Could not replace the imported file with its hydrated bundle: ${error.message}`, "warning");
    replayImport(input);
  }
}

// Capture the file-input change before app.js handles it. Plain Scenario JSON is
// opportunistically hydrated with matching repository solve fixtures. Complete
// Solve Bundles and Workbench Snapshots pass through unchanged.
document.addEventListener("change", async (event) => {
  const input = event.target;
  if (!(input instanceof HTMLInputElement) || input.id !== "file-input" || replayingImport) return;
  const [file] = input.files || [];
  if (!file) return;

  event.stopImmediatePropagation();
  try {
    const imported = JSON.parse(await file.text());
    const snapshot = imported?.snapshot_type === "workbench_snapshot_v1";
    const candidate = snapshot ? imported.solve_bundle : imported;
    const isSolveBundle = candidate?.schema_version === "1.0.0" && "recovery_columns" in candidate;
    const looksLikeScenario = imported?.scenario_id && Array.isArray(imported?.flights);

    if (snapshot || isSolveBundle || !looksLikeScenario) {
      replayImport(input);
      return;
    }
    await hydrateScenarioImport(input, file, imported);
  } catch (error) {
    // Let the existing app import handler present the canonical parse/validation error.
    replayImport(input);
  }
}, true);
