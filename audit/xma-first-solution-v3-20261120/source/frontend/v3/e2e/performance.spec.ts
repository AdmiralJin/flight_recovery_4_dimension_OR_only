import { expect, test } from "@playwright/test";
import { mkdirSync, writeFileSync } from "node:fs";
import { resolve } from "node:path";
import { entry, fixture, mockApi } from "./mock";

// Fixed, local workload. Timings are observations on this machine, not CI thresholds.
test("large draft editing, save feedback and progress stay responsive", async ({ page }) => {
  test.setTimeout(120000);
  const mock = await mockApi(page);
  const document = mock.drafts[0].document;
  const template = (document.scenario.flights as Array<Record<string, unknown>>)[0];
  document.scenario.flights = Array.from({ length: 10000 }, (_, index) => ({ ...template, flight_id: `PERF-${index}` }));
  document.manual_flight_options = Array.from({ length: 20000 }, (_, index) => ({ option_id: `OPT-${index}`, flight_id: `PERF-${index % 10000}`, origin: "AAA", destination: "BBB", delay_minutes: index % 60, notes: "fixed performance workload" }));
  mock.autoComplete = false;
  await page.goto(entry);
  await expect(page.getByLabel("研究草稿名称", { exact: true })).toBeVisible();
  const core = await page.evaluate(async () => {
    const path = "/static/workbench-v3/src/state.ts";
    const state = await import(path);
    const size = JSON.stringify(state.useWb.getState().document).length;
    const start = performance.now();
    for (let i = 0; i < 20; i++) state.isDirty();
    const dirtyCheckMs = performance.now() - start;
    return { size, dirtyCheckMs };
  });
  const editStart = Date.now();
  await page.getByLabel("研究草稿名称", { exact: true }).pressSequentially(" performance", { delay: 10 });
  const editingMs = Date.now() - editStart;
  await expect(page.getByText("未保存修改", { exact: true })).toBeVisible();
  await page.getByRole("button", { name: "保存并校验", exact: true }).click();
  await expect(page.getByText("保存与校验完成，输入已就绪。", { exact: true })).toBeVisible();
  expect(mock.saves).toBe(1);
  if (process.env.WB3_PERF_PHASE !== "before") expect(page.workers().some(worker => worker.url().includes("json.worker"))).toBe(true);
  await page.getByRole("link", { name: "配置与运行" }).first().click();
  await page.locator(".history-list button").first().click();
  await expect(page.getByText("历史事件已同步")).toBeVisible();
  const progress = await page.evaluate(async () => {
    const path = "/static/workbench-v3/src/state.ts";
    const state = await import(path);
    const event = state.useWb.getState().events[0];
    const events = Array.from({ length: 8000 }, (_, index) => ({ ...event, seq: index + 1, event_type: "solver_heartbeat", elapsed_seconds: index, message: "Fixed progress sample", metrics: { iteration: index } }));
    const start = performance.now();
    state.useWb.setState({ events });
    await new Promise<void>(done => requestAnimationFrame(() => requestAnimationFrame(() => done())));
    return { events: events.length, updateToPaintMs: performance.now() - start, hiddenPreCharacters: [...document.querySelectorAll("details:not([open]) pre")].reduce((sum, node) => sum + (node.textContent?.length ?? 0), 0) };
  });
  const result = { phase: process.env.WB3_PERF_PHASE ?? "after", recordedAt: new Date().toISOString(), ...core, editingMs, ...progress, fixture: fixture.air.draft.draft_id };
  const folder = resolve(process.cwd(), "../.workbench/v3_acceptance/performance");
  mkdirSync(folder, { recursive: true });
  writeFileSync(resolve(folder, `${result.phase}.json`), JSON.stringify(result, null, 2));
  console.log(JSON.stringify(result));
});

test("slow save and validation show their stages while navigation and theme stay responsive", async ({ page }) => {
  const mock = await mockApi(page);
  let saveReady!: () => void;
  let compileReady!: () => void;
  const saveGate = new Promise<void>(resolve => { saveReady = resolve; });
  const compileGate = new Promise<void>(resolve => { compileReady = resolve; });
  await page.route("**/api/v2/drafts/*/working-copy", async route => { await saveGate; await route.fallback(); });
  await page.route("**/api/v2/drafts/*/compile", async route => { await compileGate; await route.fallback(); });
  await page.goto(entry);
  await page.getByLabel("研究草稿名称", { exact: true }).fill("慢请求反馈验收");
  await page.getByRole("button", { name: "保存并校验", exact: true }).click();
  await expect(page.locator(".operation-progress").getByRole("status")).toHaveText("正在保存数据");
  const folder = resolve(process.cwd(), `../docs/codex_reports/assets/v3_${process.env.WB3_VISUAL_PHASE ?? "efficiency"}`);
  mkdirSync(folder, { recursive: true });
  await page.setViewportSize({ width: 1440, height: 1000 });
  await page.screenshot({ path: resolve(folder, "save_pending_1440_light.png"), fullPage: true });
  await page.getByRole("button", { name: "切换深色主题", exact: true }).click();
  await expect(page.getByRole("button", { name: "切换浅色主题", exact: true })).toBeVisible();
  await page.getByRole("link", { name: "配置与运行" }).first().click();
  await expect(page.getByRole("heading", { name: "配置与运行", exact: true })).toBeVisible();
  await expect(page.getByRole("button", { name: "开始求解", exact: true })).toBeDisabled();
  saveReady();
  await expect(page.locator(".operation-progress").getByRole("status")).toHaveText("正在校验输入与生成候选");
  await page.setViewportSize({ width: 390, height: 900 });
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1)).toBe(true);
  await page.screenshot({ path: resolve(folder, "compile_pending_390_dark.png"), fullPage: true });
  compileReady();
  await expect(page.getByRole("button", { name: "开始求解", exact: true })).toBeEnabled();
  await expect(page.locator(".operation-progress")).toHaveCount(0);
  expect(mock.saves).toBe(1);
});

test("quick save skips compilation and cannot bypass validation before running", async ({ page }) => {
  const mock = await mockApi(page);
  await page.goto(entry);
  await page.getByLabel("研究草稿名称", { exact: true }).fill("仅保存验证");
  await page.getByRole("button", { name: "仅保存", exact: true }).click();
  await expect(page.getByText("草稿与配置已保存；开始求解前仍需通过校验。", { exact: true })).toBeVisible();
  expect(mock.saves).toBe(1); expect(mock.compiles).toBe(0);
  await page.getByRole("link", { name: "配置与运行" }).first().click();
  await expect(page.getByRole("button", { name: "开始求解", exact: true })).toBeDisabled();
  await page.getByRole("button", { name: "保存并校验", exact: true }).click();
  await expect(page.getByRole("button", { name: "开始求解", exact: true })).toBeEnabled();
  expect(mock.saves).toBe(1); expect(mock.compiles).toBe(1);
});
