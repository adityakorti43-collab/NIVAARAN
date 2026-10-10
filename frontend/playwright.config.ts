import { defineConfig, devices } from "@playwright/test";

// Uses the locally installed Google Chrome (channel "chrome"), so no browser download is required.
// Expects the API on :8000 and the web app on :5173; starts them if they are not already running.
export default defineConfig({
  testDir: "./e2e",
  timeout: 90_000,
  expect: { timeout: 30_000 },
  fullyParallel: false,
  workers: 1,
  reporter: [["list"]],
  use: { baseURL: "http://localhost:5173", channel: "chrome", trace: "retain-on-failure" },
  projects: [
    { name: "desktop", use: { ...devices["Desktop Chrome"], channel: "chrome", viewport: { width: 1440, height: 900 } }, testIgnore: /(responsive|console)\.spec\.ts/ },
    { name: "mobile", use: { ...devices["Pixel 7"], channel: "chrome" }, testMatch: /responsive\.spec\.ts/ },
    { name: "console", use: { ...devices["Desktop Chrome"], channel: "chrome", viewport: { width: 1440, height: 900 } }, testMatch: /console\.spec\.ts/ },
  ],
  webServer: [
    { command: "..\\backend\\.venv\\Scripts\\python.exe -m uvicorn app.main:app --app-dir ../backend --port 8000", url: "http://127.0.0.1:8000/api/health", reuseExistingServer: true, timeout: 120_000,
      env: { NIVAARAN_DEV_OTP: "1" } },   // local test server only: phone codes are returned so the sign-in flow can be tested
    { command: "npm run dev", url: "http://localhost:5173", reuseExistingServer: true, timeout: 120_000 },
  ],
});
