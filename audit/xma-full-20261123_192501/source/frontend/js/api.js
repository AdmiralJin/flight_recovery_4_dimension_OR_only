export async function loadExample() {
  const response = await fetch("/api/examples/phase1_benchmark_001");
  if (!response.ok) throw new Error(`示例请求失败（HTTP ${response.status}）`);
  return response.json();
}

export async function loadBenchmarkPrecheckInputs() {
  return checkedJson(
    await fetch("/api/model/constraints/benchmark-inputs"),
    "Benchmark 预检查输入请求",
  );
}

export async function loadSolveExampleBundle(caseId = "phase1_benchmark_001") {
  return checkedJson(await fetch(`/api/solve/example-bundle/${encodeURIComponent(caseId)}`), "Solve Bundle 请求");
}

export async function loadCaseCatalog() {
  return getJsonWithRetry("/api/cases", "Case 目录请求");
}

export async function loadCase(caseId) {
  return getJsonWithRetry(`/api/cases/${encodeURIComponent(caseId)}`, "Case 请求");
}

async function getJsonWithRetry(url, label, attempts = 3) {
  let lastError;
  for (let attempt = 1; attempt <= attempts; attempt += 1) {
    try {
      return await checkedJson(await fetch(url, { cache: "no-store" }), label);
    } catch (error) {
      lastError = error;
      if (attempt < attempts) {
        await new Promise((resolve) => setTimeout(resolve, 250 * attempt));
      }
    }
  }
  throw lastError;
}

export async function checkSolveReadiness(bundle) {
  return checkedJson(await fetch("/api/solve/precheck", {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify(bundle),
  }), "求解就绪性请求");
}

export async function solveRecovery(bundle) {
  return checkedJson(await fetch("/api/solve", {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify(bundle),
  }), "求解请求");
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
    throw new Error(`${label}失败（HTTP ${response.status}）：${detail}`);
  }
  return payload;
}

export async function loadCanonicalCosts() {
  return checkedJson(await fetch("/api/config/costs"), "成本配置请求");
}

export async function validateCostOverrides(config) {
  return checkedJson(await fetch("/api/config/costs/validate-overrides", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(config),
  }), "成本覆盖值校验");
}

export async function loadConstraintRegistry() {
  return checkedJson(await fetch("/api/model/constraints"), "约束注册表请求");
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
  }), "约束预检查");
}
