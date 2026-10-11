import { expect, test } from "@playwright/test";
import { demoState } from "./session";

// Launch gate: every page must load without a console error, an uncaught exception or a failed API call.
let state = "";
test.beforeAll(async ({ browser }) => { state = await demoState(browser, "console"); });
test.use({ storageState: async ({}, use) => use(state) });

const PAGES = ["/?nointro", "/login", "/dashboard", "/documents", "/claim",
  "/what-if", "/assistant", "/reports", "/actions", "/settings"];

for (const path of PAGES) {
  test(`no console errors on ${path}`, async ({ page }) => {
    const problems: string[] = [];
    page.on("console", (m) => { if (m.type() === "error") problems.push(`console: ${m.text()}`); });
    page.on("pageerror", (e) => problems.push(`exception: ${e.message}`));
    page.on("response", (r) => { if (r.url().includes("/api/") && r.status() >= 500) problems.push(`HTTP ${r.status()} ${r.url()}`); });
    await page.goto(path);
    await page.waitForLoadState("networkidle");
    await page.waitForTimeout(1500);
    expect(problems).toEqual([]);
  });
}
