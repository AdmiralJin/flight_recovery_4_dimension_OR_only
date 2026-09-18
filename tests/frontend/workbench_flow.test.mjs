import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import test from "node:test";
import { fileURLToPath } from "node:url";

const projectRoot = resolve(dirname(fileURLToPath(import.meta.url)), "../..");
const html = readFileSync(resolve(projectRoot, "frontend/index.html"), "utf8");
const flowSource = readFileSync(resolve(projectRoot, "frontend/js/workbench-flow.js"), "utf8");
const css = readFileSync(resolve(projectRoot, "frontend/css/workbench.css"), "utf8");

test("workbench exposes an explicit quick flow and modal help", () => {
  for (const id of ["workflow-help-open", "workflow-help", "solve-guidance"]) {
    assert.match(html, new RegExp(`id=["']${id}["']`));
  }
  assert.match(html, /Load a case or Import JSON/);
  assert.match(html, /Solve input = READY/);
  assert.match(html, /workbench-flow\.js/);
});

test("flow helper preserves explicit scenario-only import semantics", () => {
  assert.doesNotMatch(flowSource, /\/api\/solve\/hydrate/);
  assert.doesNotMatch(flowSource, /stopImmediatePropagation\(\)/);
  assert.doesNotMatch(flowSource, /DataTransfer\(\)/);
  assert.match(flowSource, /import a complete Solve Bundle/);
  assert.match(html, /Importing Scenario JSON keeps it as Scenario-only/);
});

test("solve-disabled state is visibly different and guidance has ready/warning states", () => {
  assert.match(css, /\.button:disabled/);
  assert.match(css, /cursor: not-allowed/);
  assert.match(css, /\.solve-guidance\.is-ready/);
  assert.match(css, /\.solve-guidance\.is-warning/);
});
