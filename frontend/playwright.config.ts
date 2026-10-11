import { defineConfig, devices } from "@playwright/test";
import os from "node:os";
import path from "node:path";

// Browser tests run against their OWN servers and a throwaway database, never the site you use:
//   API on :8001 (temporary data directory, demo seeding + on-screen phone codes enabled for testing only)
//   web app on :5174, proxying /api to :8001
// Uses the locally installed Google Chrome (channel "chrome"), so no browser download is required.
export const E2E_BASE = "http://localhost:5174";
const dataDir = path.join(os.tmpdir(), `nivaaran-e2e-${Date.now()}`);
const python = path.join("..", "backend", ".venv", "Scripts", "python.exe");

export default defineConfig({
  testDir: "./e2e",
  timeout: 90_000,
  expect: { timeout: 30_000 },
  fullyParallel: false,
  workers: 1,
  reporter: [["list"]],
  use: { baseURL: E2E_BASE, channel: "chrome", trace: "retain-on-failure" },
  projects: [
    { name: "desktop", use: { ...devices["Desktop Chrome"], channel: "chrome", viewport: { width: 1440, height: 900 } }, testIgnore: /(responsive|console)\.spec\.ts/ },
    { name: "mobile", use: { ...devices["Pixel 7"], channel: "chrome" }, testMatch: /responsive\.spec\.ts/ },
    { name: "console", use: { ...devices["Desktop Chrome"], channel: "chrome", viewport: { width: 1440, height: 900 } }, testMatch: /console\.spec\.ts/ },
  ],
  webServer: [
    { command: `${python} -m uvicorn app.main:app --app-dir ../backend --port 8001`, url: "http://127.0.0.1:8001/api/health",
      reuseExistingServer: false, timeout: 180_000,
      env: { NIVAARAN_DATA_DIR: dataDir, NIVAARAN_ENABLE_DEMO: "1", NIVAARAN_NO_DOTENV: "1", NIVAARAN_TRANSLATE_PROVIDER: "test", NIVAARAN_GOOGLE_CLIENT_ID: "e2e-client.apps.googleusercontent.com", NIVAARAN_GOOGLE_CLIENT_SECRET: "e2e-not-a-secret", NIVAARAN_PUBLIC_URL: E2E_BASE, NIVAARAN_CORS_ORIGINS: E2E_BASE } },
    { command: "npx vite --port 5174 --strictPort", url: E2E_BASE, reuseExistingServer: false, timeout: 120_000,
      env: { NIVAARAN_API: "http://127.0.0.1:8001" } },
  ],
});
