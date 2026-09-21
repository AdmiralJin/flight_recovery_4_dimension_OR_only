import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import test from "node:test";
import { fileURLToPath } from "node:url";

const projectRoot = resolve(dirname(fileURLToPath(import.meta.url)), "../..");

async function importSource(relativePath) {
  const source = readFileSync(resolve(projectRoot, relativePath), "utf8");
  const moduleUrl = `data:text/javascript;base64,${Buffer.from(source).toString("base64")}`;
  return { source, module: await import(moduleUrl) };
}

const costsBundle = await importSource("frontend/js/costs.js");
const constraintsBundle = await importSource("frontend/js/constraints.js");
const caseStateBundle = await importSource("frontend/js/case-state.js");
const baseline = JSON.parse(readFileSync(
  resolve(projectRoot, "data/costs/phase2_test_costs_v1.json"),
  "utf8",
));
const html = readFileSync(resolve(projectRoot, "frontend/index.html"), "utf8");
const appSource = readFileSync(resolve(projectRoot, "frontend/js/app.js"), "utf8");

test("workbench exposes the five Current Case views and catalog workflow", () => {
  for (const id of ["data-view", "visualization-view", "recovery-view", "costs-view", "constraints-view"]) {
    assert.match(html, new RegExp(`id=["']${id}["']`));
  }
  for (const id of ["case-selector", "load-case", "import-scenario", "import-bundle", "reset-current-case"]) {
    assert.match(html, new RegExp(`id=["']${id}["']`));
  }
  assert.doesNotMatch(html, /Phase 0\.5/);
});

test("recovery controls wire solve, comparison and export without claiming production readiness", () => {
  for (const id of ["solve-recovery", "recovery-view", "recovery-mode", "export-recovered-result"]) {
    assert.match(html, new RegExp(`id=["']${id}["']`));
  }
  for (const mode of ["original", "disrupted", "recovered", "difference"]) {
    assert.match(html, new RegExp(`<option value=["']${mode}["']`));
  }
  assert.match(appSource, /const submission = \{[\s\S]*bundle: currentSolveBundle\(\)/);
  assert.match(appSource, /solveRecovery\(submission\.bundle\)/);
  assert.match(appSource, /submission\.caseId === \(workbenchState\.currentCase\?\.case_id \|\| null\)/);
  assert.match(appSource, /submission\.inputRevision === workbenchState\.inputRevision/);
  assert.match(appSource, /checkSolveReadiness\(bundle \|\| \{ scenario:/);
});

test("async validation and case loading are revision-safe and atomic", () => {
  assert.match(appSource, /let validationRequestId = 0/);
  assert.match(appSource, /revision !== workbenchState\.inputRevision/);
  assert.match(
    appSource,
    /const state = createCurrentCase\(payload\);[\s\S]*await validateScenario\(state\.scenario\)[\s\S]*workbenchState\.currentCase = state\.metadata/,
  );
  assert.match(appSource, /resultInputSnapshot/);
  assert.match(appSource, /input_snapshot: clone\(workbenchState\.resultInputSnapshot\)/);
});

test("Current Case revisions make old results stale and reset every solve input to the case baseline", () => {
  const payload = {
    case: { case_id: "C1", label: "Case 1" },
    scenario: { scenario_id: "S1", flights: [] },
    solve_bundle: {
      scenario: { scenario_id: "S1", flights: [] },
      recovery_columns: { scenario_id: "S1", flight_options: [] },
      capacity_profile: { capacity_profile_id: "CAP1", seat_capacity_by_option_id: {} },
      cost_overrides: { crew_reassignment: 100 },
    },
  };
  const state = caseStateBundle.module.createCurrentCase(payload);
  caseStateBundle.module.recordSolvedRevision(state);
  assert.equal(state.resultState, "current");
  state.costOverrides.crew_reassignment = 250;
  caseStateBundle.module.advanceInputRevision(state);
  assert.equal(state.resultState, "stale");
  assert.equal(state.inputRevision, 1);
  caseStateBundle.module.resetCurrentCaseInputs(state);
  assert.deepEqual(state.costOverrides, { crew_reassignment: 100 });
  assert.deepEqual(state.recoveryColumns, payload.solve_bundle.recovery_columns);
  assert.deepEqual(state.capacityProfile, payload.solve_bundle.capacity_profile);
});

test("Scenario-only state never invents a Solve Bundle", () => {
  const state = caseStateBundle.module.createCurrentCase({
    case: { case_id: "scenario-only", label: "Scenario only" },
    scenario: { scenario_id: "S1", flights: [] },
    solve_bundle: null,
  });
  assert.equal(caseStateBundle.module.buildCurrentSolveBundle(state), null);
  assert.equal(state.recoveryColumns, null);
  assert.equal(state.capacityProfile, null);
});

test("cost overrides change only the effective copy and reset to baseline", () => {
  const before = structuredClone(baseline);
  const effective = costsBundle.module.buildEffectiveCostProfile(
    baseline,
    { flight_delay_per_minute: 8.5 },
  );

  assert.equal(effective.coefficients.flight_delay_per_minute.value, 8.5);
  assert.deepEqual(baseline, before);
  assert.deepEqual(
    costsBundle.module.buildEffectiveCostProfile(baseline, {}),
    baseline,
  );
  for (const key of ["owner", "unit", "source", "source_reference"]) {
    assert.equal(
      effective.coefficients.flight_delay_per_minute[key],
      baseline.coefficients.flight_delay_per_minute[key],
    );
  }
});

test("cost parser rejects negative and non-finite values", () => {
  assert.throws(() => costsBundle.module.parseCostOverride("-1"), /非负数/);
  assert.throws(() => costsBundle.module.parseCostOverride("Infinity"), /有限/);
  assert.equal(costsBundle.module.parseCostOverride(""), null);
});

test("scenario and workbench export contracts stay separate", () => {
  const scenario = { scenario_id: "S1", flights: [] };
  const before = structuredClone(scenario);
  const config = costsBundle.module.buildWorkbenchConfig(
    scenario,
    baseline,
    { flight_delay_per_minute: 8.5 },
    { capacity_profile_id: "capacity-v1" },
  );

  assert.deepEqual(scenario, before);
  assert.equal("cost_overrides" in scenario, false);
  assert.deepEqual(config.cost_overrides, { flight_delay_per_minute: 8.5 });
  assert.equal(config.cost_profile_id, "phase2_test_v1");
});

test("constraint metadata grouping and status indexing are deterministic", () => {
  const metadata = [
    { constraint_id: "PRM-C01", model: "PRM" },
    { constraint_id: "SRM-C01", model: "SRM" },
    { constraint_id: "ARM-C01", model: "ARM" },
    { constraint_id: "CRM-C01", model: "CRM" },
  ];
  const grouped = constraintsBundle.module.groupConstraintMetadata(metadata);
  const indexed = constraintsBundle.module.indexPrecheckResults({
    results: [{ constraint_id: "SRM-C01", status: "passed" }],
  });

  assert.deepEqual(Object.keys(grouped), ["SRM", "ARM", "CRM", "PRM"]);
  assert.equal(grouped.PRM[0].constraint_id, "PRM-C01");
  assert.equal(indexed.get("SRM-C01").status, "passed");
});

test("constraint renderer distinguishes provenance and navigates to canonical Data state", () => {
  for (const label of ["论文约束", "实现假设", "代理约束", "固定列校验"] ) {
    assert.ok(constraintsBundle.source.includes(label));
  }
  assert.match(constraintsBundle.source, /onNavigate\(section\)/);
  assert.match(appSource, /renderConstraintInspector\([\s\S]*showDataView/);
  assert.match(appSource, /const workbenchState = \{[\s\S]*scenario:[\s\S]*costBaseline:[\s\S]*constraintMetadata:/);
});

test("frontend precheck sends Current Case Scenario, Recovery Columns, and capacity", () => {
  assert.match(appSource, /recoveryColumns: null/);
  assert.match(appSource, /passengerCapacityProfile: null/);
  assert.match(
    appSource,
    /runConstraintPrecheck\([\s\S]*workbenchState\.scenario,[\s\S]*workbenchState\.recoveryColumns,[\s\S]*workbenchState\.passengerCapacityProfile/,
  );
  assert.match(appSource, /loadCaseCatalog\(\)/);
  assert.match(appSource, /buildCurrentSolveBundle\(currentCaseState\(\)\)/);
  assert.match(appSource, /目录不可用/);
  assert.match(appSource, /重试初始化/);
  assert.doesNotMatch(appSource, /loadBenchmarkPrecheckInputs/);
});
