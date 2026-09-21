import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "@playwright/test";
import { mkdir } from "node:fs/promises";
import { fileURLToPath } from "node:url";
import { resolve } from "node:path";

const currentDirectory = fileURLToPath(new URL(".", import.meta.url));
const shots = resolve(currentDirectory, "../../docs/codex_reports/assets");

test.beforeAll(async ({ request }) => {
  const drafts = await request.get("/api/v2/drafts");
  const body = await drafts.json();
  if (!body.items?.length) {
    const created = await request.post("/api/v2/drafts", { data: { source_case_id: "benchmark-disruption-recovery" } });
    expect(created.ok()).toBeTruthy();
  }
  await mkdir(shots, { recursive: true });
});

test("root URL redirects into the v2 router instead of rendering a blank shell", async ({ page }) => {
  const messages: string[] = [];
  page.on("console", (message) => {
    if (message.type() === "error" || message.type() === "warning") messages.push(message.text());
  });
  await page.goto("/");
  await expect(page).toHaveURL(/\/workbench-v2\/data$/);
  await expect(page.getByRole("heading", { name: "数据设计" })).toBeVisible({ timeout: 15_000 });
  expect(messages.filter((message) => message.includes("basename"))).toEqual([]);
});

test("desktop task flow is compact, navigable and accessible", async ({ page }) => {
  const errors: string[] = [];
  page.on("console", (message) => message.type() === "error" && errors.push(message.text()));
  await page.setViewportSize({ width: 1440, height: 1000 });
  await page.goto("/workbench-v2/data");
  await expect(page.getByRole("heading", { name: "数据设计" })).toBeVisible({ timeout: 15_000 });
  await expect(page.getByRole("navigation", { name: "工作流导航" })).toBeVisible();
  await expect(page.locator(".data-grid")).toBeVisible();
  await page.getByRole("link", { name: "扰动影响" }).click();
  await expect(page.getByRole("heading", { name: "扰动影响" })).toBeVisible();
  await page.getByRole("button", { name: "编译并预览" }).click();
  await expect(page.getByText("Ready", { exact: true })).toBeVisible();
  await expect(page.getByRole("group", { name: "扰动影响时空网络" })).toBeVisible();
  const axe = await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa", "wcag21aa", "wcag22aa"]).analyze();
  expect(axe.violations).toEqual([]);
  expect(errors).toEqual([]);
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBeTruthy();
  await page.screenshot({ path: resolve(shots, "browser_refactor_desktop.png"), fullPage: true });
});

test("390px mode stays within viewport and keeps monitoring navigation", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("/workbench-v2/solve");
  await expect(page.getByRole("heading", { name: "实时求解" })).toBeVisible();
  await expect(page.getByRole("link", { name: "方案对比" })).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBeTruthy();
  await page.screenshot({ path: resolve(shots, "browser_refactor_mobile_390.png"), fullPage: true });
});
