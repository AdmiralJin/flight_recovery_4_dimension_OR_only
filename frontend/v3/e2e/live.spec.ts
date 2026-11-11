import { expect, test } from "@playwright/test";
const origin = process.env.WB3_LIVE_URL ?? "http://127.0.0.1:8013";

test.describe("independent database integration", () => {
  test.skip(!process.env.WB3_LIVE, "Run only against scripts/workbench_v3_preview.py on port 8013");
  test.setTimeout(90000);
  test("real AIR API: clone, save custom profile, solve snapshot, inspect audit", async ({ page }) => {
    await page.goto(`${origin}/static/workbench-v3/index.html#/prepare`);
    await page.getByRole("button", { name: "新建 / 导入" }).click();
    await page.locator(".case-card").filter({ has: page.getByRole("heading", { name: "Benchmark 扰动恢复", exact: true }) }).getByRole("button", { name: "克隆为草稿" }).click();
    await expect(page.getByRole("dialog")).toHaveCount(0);
    await page.getByLabel("研究草稿名称", { exact: true }).fill("v3 独立数据库 AIR 验收");
    await page.getByRole("link", { name: "配置与运行" }).first().click(); await page.getByLabel("求解时限（秒）", { exact: true }).fill("30");
    await page.getByRole("button", { name: "保存并校验", exact: true }).click();
    await expect(page.getByRole("button", { name: "开始求解", exact: true })).toBeEnabled(); await page.getByRole("button", { name: "开始求解", exact: true }).click();
    await expect(page.locator(".run-metrics").getByText("证明最优", { exact: true })).toBeVisible({ timeout: 50000 });
    await page.getByRole("link", { name: "结果分析" }).first().click(); await page.getByRole("button", { name: "变化对比", exact: true }).click();
    await page.getByRole("button", { name: "审计与导出", exact: true }).click(); await expect(page.getByText("一致", { exact: true })).toHaveCount(2);
    const downloading = page.waitForEvent("download"); await page.getByRole("button", { name: "导出完整审计包" }).click(); expect((await downloading).suggestedFilename()).toMatch(/\.audit\.json$/);
  });
  test("real XMA API: fixed import, coarse candidates, run and export CSV", async ({ page }) => {
    await page.goto(`${origin}/static/workbench-v3/index.html#/prepare`); await page.getByRole("button", { name: "新建 / 导入" }).click();
    await page.getByRole("button", { name: "厦航数据", exact: true }).click(); await page.getByRole("button", { name: "生成导入预览" }).click();
    await expect(page.getByText("样本已就绪")).toBeVisible({ timeout: 30000 }); await page.getByRole("button", { name: "使用预览创建草稿" }).click(); await expect(page.getByRole("dialog")).toHaveCount(0);
    await page.getByRole("link", { name: "配置与运行" }).first().click(); await page.getByLabel("候选步长（分钟）", { exact: true }).fill("60"); await page.getByLabel("最大延误（分钟）", { exact: true }).fill("120"); await page.getByLabel("求解时限（秒）", { exact: true }).fill("30");
    await page.getByRole("button", { name: "保存并校验", exact: true }).click(); await expect(page.getByRole("button", { name: "开始求解", exact: true })).toBeEnabled(); await page.getByRole("button", { name: "开始求解", exact: true }).click();
    await expect(page.locator(".run-metrics").getByText("证明最优", { exact: true })).toBeVisible({ timeout: 50000 });
    await page.getByRole("link", { name: "结果分析" }).first().click(); await page.getByRole("button", { name: "恢复方案", exact: true }).click(); await expect(page.getByText(/北京时间 UTC\+8/)).toBeVisible();
    await page.getByRole("button", { name: "旅客与容量", exact: true }).click(); const downloading = page.waitForEvent("download"); await page.getByRole("button", { name: "导出天池 11 列结果" }).click(); expect((await downloading).suggestedFilename()).toMatch(/\.csv$/);
  });
  test("v2 entry and visualization still load on the same existing server", async ({ page }) => {
    await page.goto(`${origin}/`); await expect(page).toHaveURL(/\/workbench-v2\/data/); await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
    await page.goto(`${origin}/workbench-v2/solve`); await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
    await page.goto(`${origin}/workbench-v2/visualization`); await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
  });
});
