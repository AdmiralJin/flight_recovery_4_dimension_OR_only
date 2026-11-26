import { expect, test } from "@playwright/test";
import type { Page } from "@playwright/test";
import { entry, fixture, mockApi } from "./mock";

async function chartState(page: Page, action?: "flightTip" | "passengerTip" | "costTip") {
  await expect(page.locator(".chart").first()).toBeVisible();
  return page.evaluate(async (requested) => {
    const url = performance.getEntriesByType("resource").map(item => item.name).find(name => /\/echarts_core\.js/.test(name));
    if (!url) throw new Error("ECharts module has not loaded");
    const core = await import(/* @vite-ignore */ url);
    const chart = core.getInstanceByDom(document.querySelector(".chart"));
    if (!chart) throw new Error("Chart has not mounted");
    const option = chart.getOption();
    if (requested) {
      const seriesIndex = requested === "costTip" ? 1 : option.series.findIndex((row: { data?: unknown[]; name?: string }) => row.data?.length && (requested === "passengerTip" || row.name === "航班"));
      chart.dispatchAction({ type: "showTip", seriesIndex, dataIndex: requested === "costTip" ? 3 : 0 });
    }
    const axis = (key: string) => option[key]?.map((row: { min?: unknown; max?: unknown; data?: unknown }) => ({ min: row.min, max: row.max, data: row.data }));
    return { x: axis("xAxis"), y: axis("yAxis"), zoom: option.dataZoom?.map((row: { id: string; start: number; end: number }) => ({ id: row.id, start: row.start, end: row.end })), count: option.series?.reduce((total: number, row: { data?: unknown[] }) => total + (row.data?.length ?? 0), 0) };
  }, action);
}

test("clock advances without events and active solve action is gray and disabled", async ({ page }) => {
  const mock = await mockApi(page); mock.autoComplete = false;
  await page.goto(entry); await page.getByRole("link", { name: "配置与运行" }).first().click();
  await page.getByRole("button", { name: "保存并校验", exact: true }).click();
  await page.getByRole("button", { name: "开始求解", exact: true }).click();
  const clock = page.getByTestId("run-clock"); await expect(clock).toBeVisible(); const before = await clock.textContent();
  await expect.poll(() => clock.textContent()).not.toBe(before);
  await expect(page.getByRole("button", { name: "开始求解", exact: true })).toBeDisabled();
  expect(await page.getByRole("button", { name: "开始求解", exact: true }).evaluate(el => getComputedStyle(el).filter)).toBe("grayscale(1)");
  expect(mock.creates).toBe(1);
});

test("keyword explanations work on hover and focus, formulas and algorithm details follow selection", async ({ page }) => {
  await mockApi(page); await page.goto(entry); await page.getByLabel("当前草稿", { exact: true }).selectOption(fixture.xma.draft.draft_id);
  await page.getByRole("link", { name: "配置与运行" }).first().click();
  const help = page.getByRole("button", { name: "解释：最大延误（分钟）", exact: true });
  await help.hover(); await expect(page.getByRole("tooltip")).toContainText("最大起飞延误");
  await help.focus(); await page.keyboard.press("Escape"); await expect(page.getByRole("tooltip")).toHaveCount(0);
  const limit = page.getByRole("button", { name: "解释：分配候选上限（项）", exact: true });
  await limit.focus(); await expect(page.getByRole("tooltip")).toContainText("配对数量上限");
  await page.getByRole("button", { name: "解释：目标函数", exact: true }).hover();
  await expect(page.getByRole("tooltip")).toContainText("1200"); await expect(page.getByRole("tooltip")).toContainText("r(h)");
  await page.getByLabel("目标函数", { exact: true }).selectOption("air_linear_v1");
  await page.getByRole("button", { name: "解释：目标函数", exact: true }).hover(); await expect(page.getByRole("tooltip")).toContainText("AIR 线性研究成本");
  await page.getByLabel("求解算法", { exact: true }).selectOption("benders_cg_bp");
  await page.getByRole("button", { name: "解释：求解算法", exact: true }).hover(); await expect(page.getByRole("tooltip")).toContainText("定价证据");
});

test("overview is merged, filtering preserves domains and manual horizontal/vertical zoom", async ({ page }) => {
  await mockApi(page); await page.goto(entry); await page.getByRole("link", { name: "结果分析" }).first().click();
  await page.getByLabel("分析来源", { exact: true }).selectOption("draft"); await expect(page.getByRole("img")).toBeVisible();
  await expect(page.getByRole("button", { name: "总览", exact: true })).toHaveCount(0);
  await expect(page.getByLabel("图例", { exact: true })).toContainText("换机"); await expect(page.getByLabel("图例", { exact: true })).toContainText("换组");
  const initial = await chartState(page);
  await page.getByRole("button", { name: "放大图表", exact: true }).click();
  await page.getByRole("combobox", { name: /缩放坐标/ }).selectOption("y"); await page.getByRole("button", { name: "放大图表", exact: true }).click();
  const manual = await chartState(page);
  expect(manual.zoom?.find((row: { id: string }) => row.id === "wb3-y-slider")?.start).toBeGreaterThan(0);
  await page.getByLabel("机场", { exact: true }).selectOption("A"); await page.getByLabel("变化", { exact: true }).selectOption("unchanged");
  await page.getByLabel("筛选分析航班", { exact: true }).fill("__no_matches__");
  await expect.poll(async () => (await chartState(page)).count).toBe(0);
  const filtered = await chartState(page);
  expect(filtered.x).toEqual(initial.x); expect(filtered.y).toEqual(initial.y); expect(filtered.zoom).toEqual(manual.zoom);
  expect(filtered.count).toBe(0);
  await page.getByRole("button", { name: "重置", exact: true }).click();
  await expect.poll(async () => (await chartState(page)).count).toBe(initial.count);
});

test("chart hover renders flight, passenger and cost evidence and relocated comparison remains available", async ({ page }) => {
  await mockApi(page); await page.goto(entry); await page.getByRole("link", { name: "配置与运行" }).first().click();
  await page.locator(".history-list button").first().click(); await page.getByRole("link", { name: "结果分析" }).first().click();
  await expect(page.getByRole("img")).toBeVisible(); await chartState(page, "flightTip");
  await expect(page.locator(".chart")).toContainText("计划起飞"); await expect(page.locator(".chart")).toContainText("原机尾");
  await page.getByText("方案对比与资源汇总", { exact: true }).click(); await expect(page.locator("details[open] pre").first()).toBeVisible();
  await page.getByRole("button", { name: "旅客与容量", exact: true }).click(); await chartState(page, "passengerTip");
  await expect(page.locator(".chart")).toContainText("旅客组"); await expect(page.locator(".chart")).toContainText("人数");
  await page.getByRole("button", { name: "成本与延误", exact: true }).click(); await chartState(page, "costTip");
  await expect(page.locator(".chart").first()).toContainText("占比"); await expect(page.locator(".chart").first()).toContainText("完整运行");
});
