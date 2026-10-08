import { expect, test } from "@playwright/test";
import { mkdir } from "node:fs/promises";
import { resolve } from "node:path";

test.beforeAll(async ({ request }) => {
  const existing=await (await request.get('/api/v2/drafts')).json();
  if(!existing.items?.length) await request.post('/api/v2/drafts',{data:{source_case_id:'benchmark-disruption-recovery'}});
});

test("imports XMA, selects its source objective, solves a snapshot and exports an audited plan", async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 1000 });
  await page.goto("/workbench-v2/data");
  await expect(page.getByRole("heading", { name: "厦航数据与求解配置" })).toBeVisible();
  await expect(page.locator('.case-drawer')).toHaveCount(0);
  await page.getByRole("button", { name: "读取项目厦航数据" }).click();
  await expect(page.getByText(/航班 30 班/)).toBeVisible();
  await page.getByRole("button", { name: "创建厦航研究草稿" }).click();
  await expect(page.getByLabel("厦航目标函数")).toHaveValue("tianchi_2017");
  const step = page.getByLabel("延误步长（分钟）", { exact: true });
  await step.fill("60"); await step.blur();
  await expect(page.getByLabel("厦航目标函数")).toBeEnabled();
  const delay = page.getByLabel("最大延误（分钟）", { exact: true });
  await delay.fill("120"); await delay.blur();
  await expect(page.getByLabel("厦航目标函数")).toBeEnabled();
  await page.getByRole("link", { name: "求解", exact: true }).click();
  await page.getByRole("button", { name: "创建快照并求解" }).click();
  await expect(page.getByRole("heading", { name: "厦航恢复与旅客分配" })).toBeVisible({ timeout: 30000 });
  await expect(page.getByText(/成本：11444/)).toBeVisible();
  await expect(page.getByRole("button", { name: "导出天池 11 列结果" })).toBeEnabled();
  await page.getByText("逐项评分与独立审计", { exact: true }).click();
  await expect(page.locator(".json-block")).toContainText('"valid": true');
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBeTruthy();
  const folder=resolve("../docs/codex_reports/assets"); await mkdir(folder,{recursive:true});
  await page.screenshot({path:resolve(folder,"xma_source_objective_result_20261008.png"),fullPage:true});
});
