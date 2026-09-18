import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import test from "node:test";
import { fileURLToPath } from "node:url";

const projectRoot = resolve(dirname(fileURLToPath(import.meta.url)), "../..");
const source = readFileSync(resolve(projectRoot, "frontend/js/api.js"), "utf8");
const api = await import(`data:text/javascript;base64,${Buffer.from(source).toString("base64")}`);

test("requestJson preserves a non-JSON HTTP error instead of raising a parse error", async () => {
  const originalFetch = globalThis.fetch;
  globalThis.fetch = async () => new Response("Gurobi license is unavailable", {
    status: 503,
    statusText: "Service Unavailable",
  });
  try {
    await assert.rejects(
      () => api.requestJson("/api/solve", {}, "Solve request"),
      (error) => error instanceof api.ApiError
        && error.status === 503
        && error.message.includes("Gurobi license is unavailable"),
    );
  } finally {
    globalThis.fetch = originalFetch;
  }
});

test("requestJson returns parsed JSON for successful responses", async () => {
  const originalFetch = globalThis.fetch;
  globalThis.fetch = async () => new Response(JSON.stringify({ status: "ok" }), {
    status: 200,
    headers: { "Content-Type": "application/json" },
  });
  try {
    assert.deepEqual(await api.requestJson("/api/health"), { status: "ok" });
  } finally {
    globalThis.fetch = originalFetch;
  }
});
