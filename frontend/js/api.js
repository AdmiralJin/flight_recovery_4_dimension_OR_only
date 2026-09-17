export async function loadExample() {
  return loadScenarioExample("phase1_benchmark_001");
}

export async function loadScenarioExample(caseId) {
  return requestJson(`/api/examples/${encodeURIComponent(caseId)}`, {}, "Example request");
}

export async function loadSolveExamples() {
  return requestJson("/api/solve/examples", {}, "Example list request");
}

export async function loadHealth() {
  return requestJson("/api/health", {}, "Health request");
}

export async function loadBenchmarkPrecheckInputs() {
  return checkedJson(
    await fetch("/api/model/constraints/benchmark-inputs"),
    "Benchmark precheck input request",
  );
}

export async function loadSolveExampleBundle(caseId = "phase1_benchmark_001") {
  return checkedJson(await fetch(`/api/solve/example-bundle/${encodeURIComponent(caseId)}`), "Solve bundle request");
}

export async function hydrateSolveBundle(scenario) {
  return checkedJson(await fetch("/api/solve/hydrate", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(scenario),
  }), "Solve bundle hydration request");
}

export async function checkSolveReadiness(bundle) {
  return checkedJson(await fetch("/api/solve/precheck", {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify(bundle),
  }), "Solve readiness request");
}

export async function solveRecovery(bundle) {
  return checkedJson(await fetch("/api/solve", {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify(bundle),
  }), "Solve request");
}

export async function validateScenario(data) {
  return requestJson("/api/validate", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  }, "Scenario validation request");
}

export class ApiError extends Error {
  constructor({ status, detail, payload }) {
    super(detail || `HTTP ${status}`);
    this.name = "ApiError";
    this.status = status;
    this.payload = payload;
  }
}

export async function requestJson(url, options = {}, label = "Request") {
  const response = await fetch(url, options);
  return checkedJson(response, label);
}

async function checkedJson(response, label) {
  const text = await response.text();
  let payload = null;
  if (text) {
    try { payload = JSON.parse(text); } catch { payload = { detail: text }; }
  }
  if (!response.ok) {
    const rawDetail = payload?.detail;
    const detail = typeof rawDetail === "string" ? rawDetail : JSON.stringify(rawDetail || response.statusText);
    throw new ApiError({ status: response.status, detail: `${label} failed (${response.status}): ${detail}`, payload });
  }
  return payload;
}

export async function loadCanonicalCosts() {
  return checkedJson(await fetch("/api/config/costs"), "Cost profile request");
}

export async function validateCostOverrides(config) {
  return checkedJson(await fetch("/api/config/costs/validate-overrides", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(config),
  }), "Cost override validation");
}

export async function loadConstraintRegistry() {
  return checkedJson(await fetch("/api/model/constraints"), "Constraint registry request");
}

export async function runConstraintPrecheck(scenario, recoveryColumns = null, capacityProfile = null) {
  return checkedJson(await fetch("/api/model/constraints/precheck", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      scenario,
      recovery_columns: recoveryColumns,
      capacity_profile: capacityProfile,
    }),
  }), "Constraint precheck");
}
