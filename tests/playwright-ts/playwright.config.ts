import { defineConfig, devices } from "@playwright/test";

export default defineConfig({
  testDir: "./specs",
  fullyParallel: true,
  retries: process.env.CI ? 2 : 0, // retry only in CI, where flakiness costs a whole pipeline
  reporter: [["list"], ["html", { open: "never" }], ["junit", { outputFile: "results/junit.xml" }]],
  use: {
    baseURL: process.env.GRAFANA_URL ?? "http://localhost:3000",
    viewport: { width: 1600, height: 2000 }, // tall, so Grafana renders every panel
    trace: "retain-on-failure", // a failed test leaves a trace you can replay step by step
    screenshot: "only-on-failure",
  },
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"], viewport: { width: 1600, height: 2000 } } }],
});
