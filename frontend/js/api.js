export async function loadExample() {
  const response = await fetch("/api/examples/toy_case_001");
  if (!response.ok) throw new Error(`Example request failed (${response.status})`);
  return response.json();
}

export async function validateScenario(data) {
  const response = await fetch("/api/validate", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  });
  return response.json();
}

async function checkedJson(response, label) {
  const payload = await response.json();
  if (!response.ok) {
    const detail = typeof payload.detail === "string" ? payload.detail : JSON.stringify(payload.detail);
    throw new Error(`${label} failed (${response.status}): ${detail}`);
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
