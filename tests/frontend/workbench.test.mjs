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
const stateBundle = await importSource("frontend/js/workbench-state.js");
const baseline = JSON.parse(readFileSync(
  resolve(projectRoot, "data/costs/phase2_test_costs_v1.json"),
  "utf8",
));
const html = readFileSync(resolve(projectRoot, "frontend/index.html"), "utf8");
const appSource = readFileSync(resolve(projectRoot, "frontend/js/app.js"), "utf8");

test("workbench exposes Data, Visualization, Costs, and Constraints views", () => {
  for (const id of ["data-view", "visualization-view", "costs-view", "constraints-view"]) {
    assert.match(html, new RegExp(`id=["']${id}["']`));
  }
  assert.doesNotMatch(html, /Phase 0\.5/);
});

test("recovery controls wire solve, comparison and export without claiming production readiness", () => {
  for (const id of ["solve-recovery", "recovery-view", "recovery-mode", "export-recovered-result", "export-solve-bundle"]) {
    assert.match(html, new RegExp(`id=["']${id}["']`));
  }
  for (const mode of ["original", "disrupted", "recovered", "difference"]) {
    assert.match(html, new RegExp(`<option value=["']${mode}["']`));
  }
  assert.match(appSource, /solveRecovery\(request\.bundle\)/);
  assert.match(appSource, /checkSolveReadiness\(bundle\)/);
});

test("workbench exposes the case selector, explicit readiness, health, and global error surface", () => {
  for (const id of ["example-selector", "scenario-summary", "solve-readiness-summary", "solver-summary", "result-summary", "api-health-summary", "global-toast-region", "case-metadata"]) {
    assert.match(html, new RegExp(`id=["']${id}["']`));
  }
  assert.match(appSource, /function applySolveBundle\(/);
  assert.match(appSource, /function resetToBaseline\(/);
  assert.match(appSource, /Solve result discarded because the workbench input changed/);
  assert.match(appSource, /setSolvingState\(true\)/);
});

test("example selector groups solve-ready and scenario-only cases and validates after load", () => {
  assert.match(appSource, /solveReadyGroup\.label = "Solve-ready examples"/);
  assert.match(appSource, /scenarioOnlyGroup\.label = "Scenario-only examples"/);
  assert.match(appSource, /const validation = await validateScenario\(workbenchState\.scenario\)/);
  assert.match(appSource, /workbenchState\.scenarioValidation = validation\.valid \? "valid" : "invalid"/);
});

test("solve lifecycle rejects duplicate starts and stale results", () => {
  const state = {
    solving: false, revision: 3, solveBundle: { schema_version: "1.0.0" },
    scenario: { scenario_id: "A" }, recoveryColumns: { flight_options: [] },
    passengerCapacityProfile: { capacity_profile_id: "capacity" }, costOverrides: {},
    recoveredResult: null, recoveredResultRevision: null, resultStale: false,
  };
  const request = stateBundle.module.beginSolve(state);
  assert.equal(request.revision, 3);
  assert.equal(stateBundle.module.beginSolve(state), null);
  state.revision = 4;
  assert.equal(stateBundle.module.acceptSolveResult(state, request, { status: "optimal" }), false);
  assert.equal(state.recoveredResult, null);
  stateBundle.module.finishSolve(state);
  const currentRequest = stateBundle.module.beginSolve(state);
  assert.equal(stateBundle.module.acceptSolveResult(state, currentRequest, { status: "optimal" }), true);
  assert.equal(state.recoveredResultRevision, 4);
  assert.equal(state.resultStale, false);
});

test("case baseline reset preserves bundle columns, capacity, and overrides", () => {
  const state = {
    revision: 1, dirty: false, caseId: "toy016", source: "example",
    scenario: { scenario_id: "toy016" }, solveBundle: { schema_version: "1.0.0" },
    recoveryColumns: { scenario_id: "toy016" },
    passengerCapacityProfile: { scenario_id: "toy016" },
    costOverrides: { crew_reassignment: 100 }, recoveredResult: { status: "optimal" },
    recoveredResultRevision: 1, resultStale: true,
  };
  state.baseline = stateBundle.module.snapshotCaseBaseline(state);
  state.costOverrides = {};
  state.recoveryColumns = null;
  state.dirty = true;
  assert.equal(stateBundle.module.restoreCaseBaseline(state), true);
  assert.deepEqual(state.costOverrides, { crew_reassignment: 100 });
  assert.equal(state.recoveryColumns.scenario_id, "toy016");
  assert.equal(state.revision, 2);
  assert.equal(state.recoveredResult, null);
  assert.equal(state.resultStale, false);
});

test("workbench renders scenario validity separately from case dirty and stale-result state", () => {
  assert.match(appSource, /#scenario-summary/);
  assert.match(appSource, /"MODIFIED" : "CLEAN"/);
  assert.match(appSource, /solveError \? "ERROR"/);
  assert.match(appSource, /resultStale \? "STALE RESULT"/);
  assert.match(appSource, /invalidateRecovery\(\{ markStale: hadCurrentResult \}\)/);
});

test("visualization links to Recovery without a permanently disabled Recovered Plan", () => {
  const visualizationSource = readFileSync(resolve(projectRoot, "frontend/js/visualization.js"), "utf8");
  assert.match(visualizationSource, /Open Recovery →/);
  assert.doesNotMatch(visualizationSource, /renderModeButton\("Recovered Plan"/);
});

test("case state keeps the active bundle synchronized and preserves its baseline overrides", () => {
  assert.match(appSource, /recoveryColumns = clone\(bundle\.recovery_columns\)/);
  assert.match(appSource, /passengerCapacityProfile = clone\(bundle\.capacity_profile\)/);
  assert.match(appSource, /costOverrides = clone\(bundle\.cost_overrides \|\| \{\}\)/);
  assert.match(appSource, /baseline\?\.costOverrides \|\| \{\}/);
  assert.match(appSource, /workbench_snapshot_v1/);
});

test("case cost overrides are compared against the loaded baseline, not emptiness", () => {
  assert.match(appSource, /function costOverridesMatchBaseline\(\)/);
  assert.match(appSource, /costOverridesMatchBaseline\(\) \? "baseline" : "modified"/);
  assert.match(appSource, /setCostStatus\("baseline", "Overrides restored to the current case baseline\."/);
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
  assert.throws(() => costsBundle.module.parseCostOverride("-1"), /non-negative/);
  assert.throws(() => costsBundle.module.parseCostOverride("Infinity"), /finite/);
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
  for (const label of ["PAPER", "IMPLEMENTATION ASSUMPTION", "PROXY", "FIXED-COLUMN VALIDATION"] ) {
    assert.ok(constraintsBundle.source.includes(label));
  }
  assert.match(constraintsBundle.source, /onNavigate\(section\)/);
  assert.match(appSource, /renderConstraintInspector\([\s\S]*showDataView/);
  assert.match(appSource, /const workbenchState = \{[\s\S]*scenario:[\s\S]*costBaseline:[\s\S]*constraintMetadata:/);
});

test("frontend precheck sends the current case Scenario, Recovery Columns, and capacity", () => {
  assert.match(appSource, /recoveryColumns: null/);
  assert.match(appSource, /passengerCapacityProfile: null/);
  assert.match(
    appSource,
    /runConstraintPrecheck\([\s\S]*workbenchState\.scenario,[\s\S]*workbenchState\.recoveryColumns,[\s\S]*workbenchState\.passengerCapacityProfile/,
  );
  assert.match(appSource, /currentCapacitySummary\(\)/);
  assert.doesNotMatch(appSource, /loadBenchmarkPrecheckInputs\(\)/);
});
