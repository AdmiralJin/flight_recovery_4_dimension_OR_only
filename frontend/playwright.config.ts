import { defineConfig } from "@playwright/test";

export default defineConfig({
  testDir: "./e2e",
  timeout: 45_000,
  fullyParallel: false,
  reporter: [["list"], ["html", { outputFolder: "playwright-report", open: "never" }]],
  use: {
    baseURL: "http://127.0.0.1:8000",
    channel: "msedge",
    headless: true,
    colorScheme: "dark",
    reducedMotion: "reduce",
    trace: "retain-on-failure",
  },
  webServer: {
    command: "python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000",
    cwd: "..",
    url: "http://127.0.0.1:8000/api/health",
    reuseExistingServer: true,
    timeout: 60_000,
  },
});
