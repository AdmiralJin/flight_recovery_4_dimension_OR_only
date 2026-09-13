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
