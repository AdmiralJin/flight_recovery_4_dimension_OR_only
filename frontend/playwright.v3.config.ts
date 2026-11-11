import { defineConfig } from "@playwright/test";
const phase = process.env.WB3_VISUAL_PHASE ?? (process.env.WB3_LIVE ? "live" : "task1");
export default defineConfig({
  testDir: "./v3/e2e", timeout: 45000, fullyParallel: false, workers: 1,
  reporter: [["list"], ["json", { outputFile: `../.workbench/v3_acceptance/playwright-${phase}.json` }]],
  outputDir: `../.workbench/v3_acceptance/browser-artifacts/${phase}-${process.pid}`,
  use: { baseURL: "http://127.0.0.1:5174", browserName: "chromium", channel: "msedge", headless: true, reducedMotion: "reduce", trace: "retain-on-failure" },
  webServer: process.env.WB3_LIVE ? undefined : { command: '"D:/Program Files/nodejs/node.exe" node_modules/vite/bin/vite.js --config vite.v3.config.ts', url: "http://127.0.0.1:5174/static/workbench-v3/", reuseExistingServer: true, timeout: 45000 },
});
