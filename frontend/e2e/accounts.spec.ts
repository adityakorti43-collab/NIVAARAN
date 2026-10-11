import { E2E_BASE } from "../playwright.config";
import { expect, test, type Page } from "@playwright/test";

test.describe.serial("Sign-in, persistence and isolation", () => {
  test("protected pages redirect to sign-in when signed out", async ({ page }) => {
    for (const path of ["/dashboard", "/documents", "/settings"]) {
      await page.goto(path);
      await expect(page).toHaveURL(new RegExp(`/login\\?next=${encodeURIComponent(path)}`));
    }
    await page.goto("/register");
    await expect(page).toHaveURL(/\/login$/);
  });

  test("the sign-in page offers only Google", async ({ page }) => {
    await page.goto("/login");
    const options = page.getByTestId("sign-in-options");
    await expect(options.getByRole("link", { name: /Continue with/ })).toHaveText(["Continue with Google"]);
    await expect(options.getByRole("link", { name: "privacy policy" })).toHaveAttribute("href", "/privacy");
    await expect(options.getByRole("button")).toHaveCount(0);
    await expect(page.locator("input[type=password], input[type=email]")).toHaveCount(0);
    await expect(page.getByRole("button", { name: /apple|email|password|phone/i })).toHaveCount(0);
  });

  test("Google sign-in starts a real authorization-code request with PKCE", async ({ page }) => {
    await page.goto("/login");
    await expect(page.getByTestId("google-signin")).toHaveAttribute("href", /\/api\/auth\/google\/start/);
    const href = await page.getByTestId("google-signin").getAttribute("href");
    const r = await page.request.get(href!, { maxRedirects: 0 });
    expect(r.status()).toBe(303);
    const loc = new URL(r.headers()["location"]);
    expect(loc.origin + loc.pathname).toBe("https://accounts.google.com/o/oauth2/v2/auth");
    expect(loc.searchParams.get("response_type")).toBe("code");
    expect(loc.searchParams.get("code_challenge_method")).toBe("S256");
    expect(loc.searchParams.get("redirect_uri")).toBe(`${E2E_BASE}/api/auth/google/callback`);
    expect(loc.searchParams.get("state")?.length).toBeGreaterThan(20);
    // a forged callback (unknown state) is refused, not signed in
    const forged = await page.request.get("/api/auth/google/callback?code=x&state=forged", { maxRedirects: 0 });
    expect(forged.headers()["location"]).toMatch(/^\/login\?error=/);
  });

  test("a new account starts empty; saved work and profile persist; sign-out really ends the session", async ({ browser }) => {
    // Google's consent screen can't be driven in a test, so the account comes from the test-only /api/demo/user endpoint.
    const ctx = await browser.newContext({ baseURL: E2E_BASE });
    expect((await ctx.request.post("/api/demo/user", { params: { name: "" } })).ok()).toBeTruthy();
    const page = await ctx.newPage();
    await page.goto("/dashboard");
    await expect(page.getByRole("heading", { level: 1 })).toHaveText("Welcome back");   // no invented name
    await expect(page.getByText("Your workspace is empty")).toBeVisible();              // no fake records
    expect((await page.request.post("/api/demo/load")).ok()).toBeTruthy();              // seed a known claim (test server only)
    await page.goto("/settings");
    await expect(page.getByRole("link", { name: "Link Google" })).toHaveAttribute("href", /\/api\/auth\/google\/start\?.*link=1/);
    await page.getByTestId("profile-name").fill("Kavya");
    await page.getByRole("button", { name: "Save profile" }).click();
    await expect(page.getByRole("status").filter({ hasText: "Profile saved." })).toBeVisible();
    await page.goto("/dashboard");
    await expect(page.getByRole("heading", { level: 1 })).toHaveText("Welcome back, Kavya");
    await expect(page.getByTestId("stat-payable")).toHaveText("₹99,370.00", { timeout: 60_000 });
    const cookie = (await ctx.cookies()).find((c) => c.name === "nivaaran_session")!;
    await page.getByTestId("user-menu").click();
    await page.getByTestId("sign-out").click();
    await expect(page).toHaveURL(/\/$/);
    const replay = await page.request.get("/api/auth/me", { headers: { cookie: `nivaaran_session=${cookie.value}` } });
    expect(replay.status()).toBe(401);
    await page.goto("/claim");
    await expect(page).toHaveURL(/\/login\?next=%2Fclaim/);
    await ctx.close();
  });

  test("an ended session sends the user to sign-in with an explanation", async ({ browser }) => {
    const ctx = await browser.newContext({ baseURL: E2E_BASE });
    expect((await ctx.request.post("/api/demo/user", { params: { name: "Ravi" } })).ok()).toBeTruthy();
    const page = await ctx.newPage();
    await page.goto("/dashboard");
    await expect(page.getByRole("heading", { level: 1 })).toHaveText("Welcome back, Ravi");
    await ctx.clearCookies();                       // the server no longer recognises this browser
    await page.getByRole("link", { name: "Documents" }).first().click();
    await expect(page).toHaveURL(/\/login\?next=%2Fdocuments&reason=expired/);
    await expect(page.getByText("Your session ended. Please sign in again to continue.")).toBeVisible();
    await ctx.close();
  });

  test("documents can be deleted from the page, including one a claim uses (after a second confirmation)", async ({ browser }) => {
    const ctx = await browser.newContext({ baseURL: E2E_BASE });
    expect((await ctx.request.post("/api/demo/user", { params: { name: "Deleter" } })).ok()).toBeTruthy();
    const seeded = await (await ctx.request.post("/api/demo/load")).json();
    const page = await ctx.newPage();
    await page.goto("/documents");
    await page.getByTestId(`delete-${seeded.policy_id}`).click();
    await page.getByTestId("confirm-delete").click();
    await expect(page.getByRole("alertdialog")).toContainText("saved claim");          // names the claim before deleting it
    await page.getByTestId("confirm-delete").click();
    await expect(page.getByTestId(`delete-${seeded.policy_id}`)).toHaveCount(0);
    expect((await ctx.request.get(`/api/claims/${seeded.claim_id}`)).status()).toBe(404);
    await ctx.close();
  });

  test("another account cannot read this user's claim, report or documents", async ({ browser }) => {
    const owner = await browser.newContext({ baseURL: E2E_BASE });
    expect((await owner.request.post("/api/demo/user", { params: { name: "Owner" } })).ok()).toBeTruthy();
    expect((await owner.request.post("/api/demo/load")).ok()).toBeTruthy();
    const cid = (await (await owner.request.get("/api/claims")).json())[0].claim_id;
    const did = (await (await owner.request.get("/api/documents")).json())[0].document_id;

    const other = await browser.newContext({ baseURL: E2E_BASE });
    expect((await other.request.post("/api/demo/user", { params: { name: "Other" } })).ok()).toBeTruthy();
    expect(await (await other.request.get("/api/claims")).json()).toEqual([]);
    for (const path of [`/api/claims/${cid}`, `/api/claims/${cid}/report.pdf`, `/api/claims/${cid}/chat`, `/api/claims/${cid}/fairness`,
      `/api/documents/${did}`, `/api/documents/${did}/download`, `/api/documents/${did}/pages/1.png`]) {
      expect((await other.request.get(path)).status(), path).toBe(404);
    }
    expect((await other.request.post(`/api/claims/${cid}/ask`, { data: { question: "What is covered?" } })).status()).toBe(404);
    expect((await other.request.delete(`/api/claims/${cid}`)).status()).toBe(404);
    const anon = await browser.newContext({ baseURL: E2E_BASE });
    expect((await anon.request.get(`/api/claims/${cid}`)).status()).toBe(401);
    expect((await owner.request.get(`/api/claims/${cid}`)).status()).toBe(200);
    await Promise.all([owner.close(), other.close(), anon.close()]);
  });
});

test("with only a policy uploaded, every page works from the policy", async ({ browser }) => {
  test.setTimeout(180_000);
  const ctx = await browser.newContext({ baseURL: E2E_BASE });
  expect((await ctx.request.post("/api/demo/user", { params: { name: "Policy only" } })).ok()).toBeTruthy();
  const pdf = (await import("node:fs")).readFileSync((await import("node:path")).resolve("..", "sample-documents", "Sample_Health_Insurance_Policy.pdf"));
  expect((await ctx.request.post("/api/documents", { multipart: { file: { name: "policy.pdf", mimeType: "application/pdf", buffer: pdf } } })).ok()).toBeTruthy();
  const page = await ctx.newPage();
  await page.goto("/dashboard");
  await expect(page.getByText("Arogya Kavach Family Floater").first()).toBeVisible();
  await expect(page.getByText("Your workspace is empty")).toHaveCount(0);
  await page.goto("/what-if");
  await page.getByLabel("Charge 1 amount").fill("24000");
  await page.getByTestId("run-estimate").click();
  await expect(page.getByTestId("estimate-result")).toContainText("Your policy would likely pay", { timeout: 60_000 });
  expect((await ctx.request.get("/api/claims").then((r) => r.json())).length).toBe(0);      // estimates are never saved
  await page.goto("/assistant");
  await page.getByRole("button", { name: "Is room rent capped?" }).first().click();
  await expect(page.getByTestId("policy-answer").first()).toContainText("2.2", { timeout: 60_000 });
  await page.goto("/actions");
  await expect(page.getByText("Discharge summary")).toBeVisible();
  await page.goto("/reports");
  const pdfHref = await page.getByTestId("download-policy-pdf").getAttribute("href");
  expect((await ctx.request.get(pdfHref!)).headers()["content-type"]).toBe("application/pdf");
  await ctx.close();
});

test("the whole site can be shown in an Indian language, and back in English", async ({ browser }) => {
  // The test server uses a stand-in translator that marks text as "⟦ta⟧ …"; real servers use Azure AI Translator.
  const ctx = await browser.newContext({ baseURL: E2E_BASE });
  expect((await ctx.request.post("/api/demo/user", { params: { name: "Lang" } })).ok()).toBeTruthy();
  const page = await ctx.newPage();
  await page.goto("/dashboard");
  await page.getByTestId("language-picker").click();
  await expect(page.getByTestId("lang-ta")).toContainText("தமிழ்");
  await expect(page.getByTestId("lang-mni")).toBeVisible();
  await page.getByTestId("lang-ta").click();
  await expect(page.getByRole("heading", { level: 1 })).toContainText("⟦ta⟧", { timeout: 15_000 });
  await page.getByRole("link", { name: /Documents/ }).first().click();            // new page text is translated as it appears
  await expect(page.getByRole("heading", { level: 1 })).toContainText("⟦ta⟧", { timeout: 15_000 });
  await page.reload();                                                            // the choice is remembered
  await expect(page.getByRole("heading", { level: 1 })).toContainText("⟦ta⟧", { timeout: 15_000 });
  await page.getByTestId("language-picker").click();
  await page.getByTestId("lang-en").click();
  await expect(page.getByRole("heading", { level: 1 })).not.toContainText("⟦");
  await ctx.close();
});
