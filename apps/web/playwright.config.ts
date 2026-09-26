import { defineConfig, devices } from "@playwright/test";

const externalBaseUrl = process.env.PLAYWRIGHT_BASE_URL;

export default defineConfig({
  testDir: "./tests/e2e",
  use: { baseURL: externalBaseUrl ?? "http://127.0.0.1:3000", trace: "on-first-retry" },
  webServer: externalBaseUrl
    ? undefined
    : { command: "npm run dev", url: "http://127.0.0.1:3000", reuseExistingServer: true },
  projects: [
    { name: "desktop", use: { ...devices["Desktop Chrome"] } },
    { name: "mobile", use: { ...devices["Pixel 7"] } }
  ]
});
