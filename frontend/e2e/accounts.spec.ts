import { expect, test } from "@playwright/test";

const PW = "evidence-first-42";

test.describe.serial("Accounts, persistence and isolation", () => {
  const email = `e2e-${Date.now()}@example.com`;

  test("protected pages redirect to sign-in when signed out", async ({ page }) => {
    await page.goto("/dashboard");
    await expect(page).toHaveURL(/\/login\?next=%2Fdashboard/);
    await expect(page.getByRole("heading", { level: 1 })).toHaveText("Sign in");
  });

  test("registration validates input, then signs in to an empty workspace", async ({ page }) => {
    await page.goto("/register");
    await page.getByTestId("register-name").fill("Asha Rao");
    await page.getByTestId("register-email").fill(email);
    await page.locator("#new-password").fill("short");
    await page.getByRole("button", { name: "Create account" }).click();
    await expect(page.getByRole("alert")).toContainText("at least 10 characters");
    await page.locator("#new-password").fill(PW);
    await page.getByRole("button", { name: "Create account" }).click();
    await expect(page).toHaveURL(/\/dashboard/);
    await expect(page.getByRole("heading", { level: 1 })).toHaveText("Welcome back, Asha");
    await expect(page.getByText("Your workspace is empty")).toBeVisible();   // no fake records for a new user
  });

  test("saved work survives sign-out and sign-in", async ({ page }) => {
    await page.goto("/login");
    await page.getByTestId("login-email").fill(email);
    await page.locator("#password").fill(PW);
    await page.getByRole("button", { name: "Sign in" }).click();
    await expect(page).toHaveURL(/\/dashboard/);
    await page.getByRole("button", { name: "Add the synthetic demo case" }).click();
    await expect(page.getByTestId("stat-payable")).toHaveText("₹99,370.00", { timeout: 60_000 });
    await page.getByTestId("user-menu").click();
    await page.getByTestId("sign-out").click();
    await expect(page).toHaveURL(/\/$/);   // lands on the home page, not the sign-in redirect
    await page.goto("/claim");
    await expect(page).toHaveURL(/\/login/);
    await page.getByTestId("login-email").fill(email);
    await page.locator("#password").fill(PW);
    await page.getByRole("button", { name: "Sign in" }).click();
    await expect(page).toHaveURL(/\/claim$/);   // returns to the page that asked for sign-in
    await expect(page.getByTestId("ledger")).toBeVisible();
    await expect(page.getByTestId("claim-payable")).toContainText("₹99,370.00");
  });

  test("wrong password is rejected", async ({ page }) => {
    await page.goto("/login");
    await page.getByTestId("login-email").fill(email);
    await page.locator("#password").fill("not-the-password-1");
    await page.getByRole("button", { name: "Sign in" }).click();
    await expect(page.getByRole("alert")).toBeVisible();
    await expect(page).toHaveURL(/\/login/);
  });

  test("another account cannot read this user's claim, report or documents", async ({ browser }) => {
    const owner = await browser.newContext({ baseURL: "http://localhost:5173" });
    expect((await owner.request.post("/api/auth/login", { data: { email, password: PW } })).ok()).toBeTruthy();
    const claims = await (await owner.request.get("/api/claims")).json();
    const docs = await (await owner.request.get("/api/documents")).json();
    const cid = claims[0].claim_id, did = docs[0].document_id;

    const other = await browser.newContext({ baseURL: "http://localhost:5173" });
    expect((await other.request.post("/api/demo/enter")).ok()).toBeTruthy();
    for (const path of [`/api/claims/${cid}`, `/api/claims/${cid}/report.pdf`, `/api/claims/${cid}/chat`, `/api/claims/${cid}/fairness`,
      `/api/documents/${did}`, `/api/documents/${did}/download`, `/api/documents/${did}/pages/1.png`]) {
      expect((await other.request.get(path)).status(), path).toBe(404);
    }
    expect((await other.request.post(`/api/claims/${cid}/ask`, { data: { question: "What is covered?" } })).status()).toBe(404);
    expect((await other.request.delete(`/api/claims/${cid}`)).status()).toBe(404);
    // and signed-out requests are refused outright
    const anon = await browser.newContext({ baseURL: "http://localhost:5173" });
    expect((await anon.request.get(`/api/claims/${cid}`)).status()).toBe(401);
    await Promise.all([owner.close(), other.close(), anon.close()]);
  });
});

test.describe("Other sign-in methods", () => {
  test("phone number sign-in: send a code, verify it, land in a new workspace", async ({ page }) => {
    // A fresh number each run; the local API runs with NIVAARAN_DEV_OTP=1, so the code is shown on screen.
    const phone = `9${String(Date.now()).slice(-9)}`;
    await page.goto("/login");
    await page.getByTestId("phone-signin").click();
    await page.getByTestId("phone-input").fill(phone);
    await page.getByRole("button", { name: "Send code" }).click();
    const code = (await page.getByTestId("dev-code").textContent())?.trim() ?? "";
    expect(code).toMatch(/^\d{6}$/);
    await page.getByTestId("otp-input").fill(code === "000000" ? "111111" : "000000");
    await page.getByRole("button", { name: "Verify and continue" }).click();
    await expect(page.getByRole("alert")).toContainText("isn't right");
    await page.getByTestId("otp-input").fill(code);
    await page.getByLabel("Your name (new accounts only, optional)").fill("Kavya");
    await page.getByRole("button", { name: "Verify and continue" }).click();
    await expect(page).toHaveURL(/\/dashboard/);
    await expect(page.getByRole("heading", { level: 1 })).toHaveText("Welcome back, Kavya");
    await page.goto("/settings");
    await expect(page.getByText("Signed in with a phone code")).toBeVisible();
    await expect(page.getByRole("button", { name: "Set a password" })).toBeVisible();
  });

  test("Google and Apple buttons are shown, and say when the server isn't configured for them", async ({ page }) => {
    await page.goto("/login");
    const social = page.getByTestId("social-signin");
    await expect(social.getByText("Continue with Google")).toBeVisible();
    await expect(social.getByText("Continue with Apple")).toBeVisible();
    const providers = await (await page.request.get("/api/auth/providers")).json();
    if (!providers.google) await expect(social.getByRole("button", { name: /Continue with Google/ })).toBeDisabled();
    else await expect(page.getByTestId("google-signin")).toHaveAttribute("href", /\/api\/auth\/google\/start/);
  });
});
