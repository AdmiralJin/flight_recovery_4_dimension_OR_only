import { expect, test } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";
import { mkdirSync } from "node:fs";
import { resolve } from "node:path";
import { entry, fixture, mockApi } from "./mock";

test("AIR: clone, edit, validate, configure, submit once, inspect and export", async ({ page }) => {
  const mock = await mockApi(page); await page.goto(entry);
  await expect(page.getByLabel("研究草稿名称", { exact: true })).toHaveValue(fixture.air.draft.name);
  await page.getByRole("button", { name: "新建 / 导入" }).click();
  await page.getByRole("button", { name: "克隆为草稿" }).first().click();
  await expect(page.getByRole("dialog")).toHaveCount(0);
  await page.getByLabel("研究草稿名称", { exact: true }).fill("AIR 交互验收");
  await page.getByRole("link", { name: "配置与运行" }).first().click();
  await expect(page.getByRole("button", { name: "开始求解", exact: true })).toBeDisabled();
  await page.getByLabel("求解时限（秒）", { exact: true }).fill("30");
  await page.getByRole("button", { name: "保存并校验", exact: true }).click();
  await expect(page.getByRole("button", { name: "开始求解", exact: true })).toBeEnabled();
  await page.getByRole("button", { name: "开始求解", exact: true }).evaluate((el: HTMLButtonElement) => { el.click(); el.click(); });
  await expect.poll(() => mock.creates).toBe(1);
  await page.getByRole("link", { name: "结果分析" }).first().click();
  await expect(page.getByText("证明最优", { exact: true }).first()).toBeVisible({ timeout: 15000 });
  await page.getByRole("button", { name: "变化对比", exact: true }).click();
  await page.getByRole("button", { name: "审计与导出", exact: true }).click();
  const download = page.waitForEvent("download"); await page.getByRole("button", { name: "导出完整审计包" }).click();
  expect((await download).suggestedFilename()).toMatch(/\.audit\.json$/);
});

test("XMA: random import, target parameters, save, start and cancel", async ({ page }) => {
  const mock = await mockApi(page); mock.autoComplete = false; await page.goto(entry);
  await page.getByRole("button", { name: "新建 / 导入" }).click(); await page.getByRole("button", { name: "厦航数据", exact: true }).click();
  await page.getByLabel("抽样方式", { exact: true }).selectOption("random"); await page.getByLabel("随机种子", { exact: true }).fill("20261106");
  await page.getByRole("button", { name: "生成导入预览" }).click(); await expect(page.getByText("样本已就绪")).toBeVisible();
  await page.getByRole("button", { name: "使用预览创建草稿" }).click(); await expect(page.getByRole("dialog")).toHaveCount(0);
  await page.getByRole("link", { name: "配置与运行" }).first().click();
  await page.getByLabel("求解算法", { exact: true }).selectOption("benders_joint"); await page.getByLabel("目标函数", { exact: true }).selectOption("air_linear_v1");
  await page.getByLabel("候选步长（分钟）", { exact: true }).fill("60"); await page.getByLabel("最大延误（分钟）", { exact: true }).fill("120");
  await page.getByRole("button", { name: "保存并校验", exact: true }).click(); await page.getByRole("button", { name: "开始求解", exact: true }).click();
  await expect(page.getByRole("button", { name: "取消运行", exact: true })).toBeVisible(); await page.getByRole("button", { name: "取消运行", exact: true }).click();
  await expect(page.getByText("已取消", { exact: true }).first()).toBeVisible(); expect(mock.creates).toBe(1);
});

test("draft switching offers save / discard / cancel and workspace navigation retains edits", async ({ page }) => {
  await mockApi(page); await page.goto(entry); const field = page.getByLabel("研究草稿名称", { exact: true }); await expect(field).toBeVisible(); await field.fill("本地修改");
  await page.getByLabel("当前草稿", { exact: true }).selectOption(fixture.xma.draft.draft_id);
  await expect(page.getByRole("dialog", { name: "保留未保存的修改？" })).toBeVisible(); await page.getByRole("button", { name: "取消", exact: true }).click();
  await expect(field).toHaveValue("本地修改");
  await page.getByRole("link", { name: "结果分析" }).first().click(); await page.getByRole("link", { name: "数据准备" }).first().click(); await expect(field).toHaveValue("本地修改");
  await page.getByLabel("当前草稿", { exact: true }).selectOption(fixture.xma.draft.draft_id); await page.getByRole("button", { name: "放弃修改" }).click();
  await expect(field).toHaveValue(fixture.xma.draft.name);
});

test("version conflict and network failure preserve local edits", async ({ page }) => {
  const mock = await mockApi(page); await page.goto(entry); const field = page.getByLabel("研究草稿名称", { exact: true }); await field.fill("冲突时的本地修改"); mock.conflict = true;
  await page.getByRole("button", { name: "保存并校验", exact: true }).click(); await expect(page.getByText("版本冲突：本地修改已保留。", { exact: false })).toBeVisible(); await expect(field).toHaveValue("冲突时的本地修改");
  mock.conflict = false; mock.networkSave = true; await page.getByRole("button", { name: "保存并校验", exact: true }).click(); await expect(field).toHaveValue("冲突时的本地修改");
  mock.networkSave = false; await page.getByRole("button", { name: "保存并校验", exact: true }).click(); await expect(page.getByText("已保存 · 校验通过")).toBeVisible();
});

test("advanced invalid JSON cannot run, and raw edits survive navigation", async ({ page }) => {
  await mockApi(page); await page.goto(entry); await page.getByRole("button", { name: "高级数据", exact: false }).click(); await page.getByText("完整草稿 JSON · 候选 / 配置 / 高级结构", { exact: true }).click();
  await page.getByLabel("完整草稿 JSON", { exact: true }).fill("{ invalid"); await page.getByRole("button", { name: "保存并校验", exact: true }).click();
  await expect(page.getByRole("alert")).toBeVisible(); await page.getByRole("link", { name: "配置与运行" }).first().click(); await expect(page.getByRole("button", { name: "开始求解", exact: true })).toBeDisabled();
  await page.getByRole("link", { name: "数据准备" }).first().click(); await page.getByRole("button", { name: "高级数据", exact: false }).click(); await page.getByText("完整草稿 JSON · 候选 / 配置 / 高级结构", { exact: true }).click(); await expect(page.getByLabel("完整草稿 JSON", { exact: true })).toHaveValue("{ invalid");
});

test("refresh restores run and event history; old draft requests cannot overwrite selection", async ({ page }) => {
  const mock = await mockApi(page); await page.goto(entry); await expect(page.getByLabel("研究草稿名称", { exact: true })).toBeVisible();
  mock.draftDelay = fixture.air.draft.draft_id; await page.getByLabel("当前草稿", { exact: true }).selectOption(fixture.air.draft.draft_id); await page.getByLabel("当前草稿", { exact: true }).selectOption(fixture.xma.draft.draft_id);
  await expect(page.getByLabel("研究草稿名称", { exact: true })).toHaveValue(fixture.xma.draft.name); await page.waitForTimeout(800); await expect(page.getByLabel("研究草稿名称", { exact: true })).toHaveValue(fixture.xma.draft.name);
  await page.getByRole("link", { name: "配置与运行" }).first().click(); await page.locator(".history-list button").first().click(); await expect(page.getByText("历史事件已同步")).toBeVisible();
  await page.reload(); await expect(page.getByText("历史事件已同步")).toBeVisible(); await expect(page.getByText("证明最优", { exact: true }).first()).toBeVisible();
});

test("infeasible and unconverged results keep their real states and mode availability", async ({ page }) => {
  const mock = await mockApi(page); mock.runs[0].optimization_status = "infeasible"; await page.goto(entry); await page.getByRole("link", { name: "配置与运行" }).first().click();
  await page.locator(".history-list button").first().click(); await page.getByRole("link", { name: "结果分析" }).first().click(); await expect(page.getByRole("button", { name: "恢复方案", exact: true })).toBeDisabled(); await expect(page.getByText("认证不可行", { exact: true }).first()).toBeVisible();
  mock.runs[0].optimization_status = "not_converged"; await page.reload(); await expect(page.getByText("未收敛", { exact: true }).first()).toBeVisible();
});

test("empty states and keyboard modal focus are usable", async ({ page }) => {
  await mockApi(page, true); await page.goto(entry); await expect(page.getByText("从一个研究草稿开始")).toBeVisible();
  await expect(page.getByText("未选择草稿", { exact: true })).toBeVisible();
  await page.getByRole("button", { name: "新建 / 导入" }).click(); await expect(page.getByRole("dialog")).toBeVisible(); await page.keyboard.press("Escape"); await expect(page.getByRole("dialog")).toHaveCount(0);
  await expect(page.getByRole("button", { name: "新建 / 导入" })).toBeFocused(); await page.getByRole("link", { name: "配置与运行" }).first().click(); await expect(page.getByRole("button", { name: "开始求解", exact: true })).toBeDisabled();
  await page.getByRole("link", { name: "结果分析" }).first().click(); await expect(page.getByText("暂无可分析的数据")).toBeVisible();
});

test("record forms protect identifiers, edit fields, and retain changes until saved", async ({ page }) => {
  const mock = await mockApi(page); await page.goto(entry);
  await page.getByRole("button", { name: "编辑记录 F1", exact: true }).click();
  await expect(page.getByLabel("航班 ID", { exact: true })).toHaveAttribute("readonly", "");
  await page.getByLabel("最大延误（分钟）", { exact: true }).fill("90");
  await page.getByRole("button", { name: "关闭编辑", exact: true }).click();
  await expect(page.getByRole("dialog", { name: "保留未保存的修改？" })).toBeVisible();
  await page.getByRole("button", { name: "保存后继续", exact: true }).click();
  await expect(page.getByRole("dialog")).toHaveCount(0); expect(mock.saves).toBe(1);
  expect((mock.drafts[0].document.scenario.flights as Array<{ max_delay: number }>)[0].max_delay).toBe(90);
});

test("JSON import and saving before switching create separate draft copies", async ({ page }) => {
  const mock = await mockApi(page); await page.goto(entry); await page.getByLabel("研究草稿名称", { exact: true }).fill("要保留的修改");
  await page.getByLabel("当前草稿", { exact: true }).selectOption(fixture.xma.draft.draft_id); await page.getByRole("button", { name: "保存后继续" }).click();
  await expect(page.getByLabel("研究草稿名称", { exact: true })).toHaveValue(fixture.xma.draft.name); expect(mock.drafts.find(d => d.draft_id === fixture.air.draft.draft_id)?.name).toBe("要保留的修改");
  await page.getByRole("button", { name: "新建 / 导入" }).click(); await page.getByRole("button", { name: "JSON 导入", exact: true }).click();
  await page.getByLabel("草稿 JSON 文件", { exact: true }).setInputFiles({ name: "draft.json", mimeType: "application/json", buffer: Buffer.from(JSON.stringify(fixture.air.draft.document)) });
  await page.getByRole("button", { name: "导入为新草稿" }).click(); await expect(page.getByRole("dialog")).toHaveCount(0); expect(mock.drafts).toHaveLength(3);
});

test("XMA results preserve timezone, all resource views, comparison and CSV export", async ({ page }) => {
  await mockApi(page); await page.goto(entry); await page.getByLabel("当前草稿", { exact: true }).selectOption(fixture.xma.draft.draft_id);
  await page.getByRole("link", { name: "配置与运行" }).first().click(); await page.locator(".history-list button").first().click(); await page.getByRole("link", { name: "结果分析" }).first().click();
  await expect(page.getByText(/北京时间 UTC\+8/)).toBeVisible(); await page.getByRole("button", { name: "变化对比", exact: true }).click();
  await page.getByRole("button", { name: "航班与资源", exact: true }).click(); await page.getByLabel("资源图层", { exact: true }).selectOption("aircraft"); await expect(page.getByRole("img")).toBeVisible();
  await page.getByLabel("资源图层", { exact: true }).selectOption("crew"); await expect(page.getByText("No crew are defined.", { exact: true })).toBeVisible();
  await page.getByRole("button", { name: "旅客与容量", exact: true }).click(); const download = page.waitForEvent("download"); await page.getByRole("button", { name: "导出天池 11 列结果" }).click(); expect((await download).suggestedFilename()).toMatch(/\.csv$/);
});

test("large tables remain virtualized and keyboard chart zoom is available", async ({ page }) => {
  const mock = await mockApi(page);
  const template = (mock.drafts[0].document.scenario.flights as Array<Record<string, unknown>>)[0];
  mock.drafts[0].document.scenario.flights = Array.from({ length: 10000 }, (_, index) => ({ ...template, flight_id: `TEST-${index + 1}` }));
  await page.goto(entry); await expect(page.getByRole("button", { name: "编辑记录 TEST-1", exact: true })).toBeVisible();
  expect(await page.getByRole("row").count()).toBeLessThan(40);
  await page.getByLabel("筛选表格", { exact: true }).fill("TEST-10000"); await expect(page.getByRole("button", { name: "编辑记录 TEST-10000", exact: true })).toBeVisible();
  await page.getByRole("link", { name: "结果分析" }).first().click();
  await page.getByRole("button", { name: "放大图表", exact: true }).click(); await page.getByRole("button", { name: "缩小图表", exact: true }).click(); await page.getByRole("button", { name: "重置图表范围", exact: true }).click();
  await expect(page.getByRole("img")).toBeVisible();
});

for (const theme of ["light", "dark"] as const) test(`XMA long sample names fit narrow screen ${theme}`, async ({ page }) => {
  await mockApi(page); await page.setViewportSize({ width: 390, height: 900 }); await page.addInitScript(value => localStorage.setItem("wb3.theme", value), theme); await page.goto(entry);
  await page.getByLabel("当前草稿", { exact: true }).selectOption(fixture.xma.draft.draft_id); await expect(page.getByLabel("研究草稿名称", { exact: true })).toHaveValue(fixture.xma.draft.name);
  const dir = resolve(process.cwd(), `../docs/codex_reports/assets/v3_${process.env.WB3_VISUAL_PHASE ?? "task2"}`); mkdirSync(dir, { recursive: true });
  for (const route of ["prepare", "run", "results"]) {
    await page.goto(`/static/workbench-v3/#/${route}`); await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
    if (route === "prepare") await expect(page.getByLabel("研究草稿名称", { exact: true })).toHaveValue(fixture.xma.draft.name);
    if (route === "results") await expect(page.getByText(/北京时间 UTC\+8/)).toBeVisible();
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth + 1)).toBe(true);
    await page.screenshot({ path: resolve(dir, `xma_${route}_390_${theme}.png`), fullPage: true, animations: "disabled" });
  }
});

for (const width of [1440, 1024, 390]) for (const theme of ["light", "dark"] as const) {
  test(`visual and accessibility ${width} ${theme}`, async ({ page }) => {
    await mockApi(page); await page.setViewportSize({ width, height: 1000 }); await page.addInitScript(value => localStorage.setItem("wb3.theme", value), theme); await page.goto(entry);
    await expect(page.getByLabel("研究草稿名称", { exact: true })).toBeVisible();
    const phase = process.env.WB3_VISUAL_PHASE ?? "task1"; const dir = resolve(process.cwd(), `../docs/codex_reports/assets/v3_${phase}`); mkdirSync(dir, { recursive: true });
    const errors: string[] = []; page.on("pageerror", error => errors.push(error.message));
    for (const route of ["prepare", "run", "results"]) {
      await page.goto(`/static/workbench-v3/#/${route}`); await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
      if (route === "results") { await page.getByLabel("分析来源", { exact: true }).selectOption("draft"); await expect(page.getByRole("img").first()).toBeVisible(); }
      await page.screenshot({ path: resolve(dir, `${route}_${width}_${theme}.png`), fullPage: true, animations: "disabled" });
      expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth + 1)).toBe(true);
      const axe = await new AxeBuilder({ page }).include(".wb3-app").withTags(["wcag2a", "wcag2aa", "wcag21aa"]).analyze();
      expect(axe.violations.map(v => ({ id: v.id, nodes: v.nodes.map(n => n.target) }))).toEqual([]);
    }
    expect(errors).toEqual([]);
  });
}
