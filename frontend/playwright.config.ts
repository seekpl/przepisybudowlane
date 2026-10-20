import { defineConfig, devices } from "@playwright/test";

// Aplikacja (frontend + backend z treściami startowymi) musi już działać — w CI startuje ją workflow.
export default defineConfig({
  testDir: "./e2e",
  timeout: 30_000,
  retries: process.env.CI ? 1 : 0,
  reporter: process.env.CI ? [["list"], ["html", { open: "never" }]] : "list",
  use: {
    baseURL: process.env.E2E_BASE_URL ?? "http://localhost:3000",
    locale: "pl-PL",
    trace: "retain-on-failure",
  },
  projects: [
    { name: "komputer", use: { ...devices["Desktop Chrome"], viewport: { width: 1280, height: 900 } } },
    { name: "telefon", use: { ...devices["Desktop Chrome"], viewport: { width: 375, height: 760 }, hasTouch: true } },
  ],
});
