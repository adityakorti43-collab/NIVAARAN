import { expect, test } from "@playwright/test";
import { demoState } from "./session";

let state = "";
test.beforeAll(async ({ browser }) => { state = await demoState(browser, "mobile"); });
test.use({ storageState: async ({}, use) => use(state) });

for (const path of ["/?nointro", "/login", "/dashboard", "/fairness", "/actions", "/claim", "/what-if", "/evaluation", "/costs"]) {
  test(`no horizontal page scroll on ${path}`, async ({ page }) => {
    await page.goto(path);
    await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
    const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
    expect(overflow).toBeLessThanOrEqual(1);
  });
}

test("mobile menu opens and navigates", async ({ page }) => {
  await page.goto("/dashboard");
  await page.getByRole("button", { name: "Open menu" }).click();
  await page.getByRole("link", { name: "Claim workspace" }).click();
  await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Itemised adjudication ledger" })).toBeVisible();   // table becomes cards on phones
});
