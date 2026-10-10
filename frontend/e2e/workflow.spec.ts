import { expect, test } from "@playwright/test";
import { demoState } from "./session";

let state = "";
test.describe.serial("Nivaaran demo workflow", () => {
  test.beforeAll(async ({ browser }) => { state = await demoState(browser, "workflow"); });
  test.use({ storageState: async ({}, use) => use(state) });

  test("dashboard shows the user's own records and the engine estimate", async ({ page }) => {
    await page.goto("/dashboard");
    await expect(page).toHaveTitle(/Nivaaran/);
    await expect(page.getByRole("heading", { level: 1 })).toHaveText("Welcome to the demo workspace");
    await expect(page.getByText("Demo data.")).toBeVisible();
    await expect(page.getByTestId("stat-payable")).toHaveText("₹99,370.00");   // exact value, never an interpolated one
    await expect(page.getByTestId("claims-list")).toContainText("appendicectomy");
  });

  test("navigation reaches every workspace", async ({ page }) => {
    await page.goto("/dashboard");
    const pages: [string, RegExp][] = [
      ["Documents", /Policy documents and versions/], ["Claim workspace", /appendicectomy/i], ["Evidence explorer", /Inspect retrieval/],
      ["Claim map", /How each charge connects/], ["Money flow", /From billed amount/], ["What-if calculator", /Explore scenarios/],
      ["Assistant", /Ask about your policy/], ["Mismatch checks", /Do your documents tell the same story/], ["Next steps", /What to do next/],
      ["Treatment costs", /What might a treatment cost/], ["Evaluation", /Keyword baseline vs semantic/], ["Reports", /Export the claim analysis/],
    ];
    for (const [link, heading] of pages) {
      await page.getByRole("navigation", { name: "Main" }).getByRole("link", { name: link }).click();
      await expect(page.getByRole("heading", { level: 1 })).toHaveText(heading);
    }
  });

  test("ledger row expands to show clause evidence with page reference", async ({ page }) => {
    await page.goto("/claim");
    await expect(page.getByTestId("ledger")).toBeVisible();
    await page.getByTestId("row-13").click(); // TV & telephone charges
    await expect(page.getByText("Television, telephone, laundry and attendant charges are not payable.").first()).toBeVisible();
    await expect(page.getByText(/Policy · p\. 3/).first()).toBeVisible();
    await page.getByTestId("row-12").click(); // Nebulizer kit
    await expect(page.getByText(/Item-specific clauses disagree/).first()).toBeVisible();
  });

  test("applicable policy version is chosen from the treatment date", async ({ page }) => {
    await page.goto("/claim");
    await expect(page.getByTestId("version-label")).toContainText("E-01");
  });

  test("before/after comparison explains the endorsement", async ({ page }) => {
    await page.goto("/claim");
    const cmp = page.getByTestId("comparison");
    await expect(cmp).toContainText("Clause 2.2 is replaced by E1.1");
    await expect(cmp).toContainText("+₹12,880.00");
  });

  test("what-if recalculates with the rules engine, is labelled hypothetical, and can be saved", async ({ page }) => {
    await page.goto("/what-if");
    await page.getByLabel("Co-payment (%)").fill("0");
    await page.getByTestId("run-scenario").click();
    await expect(page.getByText("Hypothetical scenario.").first()).toBeVisible();
    await expect(page.getByTestId("comparison")).toContainText("₹1,04,600.00");
    await page.getByTestId("scenario-name").fill("No co-payment");
    await page.getByTestId("save-scenario").click();
    await expect(page.getByTestId("saved-scenarios")).toContainText("No co-payment");
    // the saved analysis itself is unchanged
    await page.goto("/dashboard");
    await expect(page.getByTestId("stat-payable")).toHaveText("₹99,370.00");
  });

  test("assistant answers with grounded citations and admits missing evidence", async ({ page }) => {
    await page.goto("/assistant");
    await page.getByRole("button", { name: "Why was the room charge reduced?" }).click();
    await expect(page.getByTestId("answer").last()).toContainText("partially payable");
    await page.getByTestId("ask-input").fill("Is dental scaling covered?");
    await page.getByRole("button", { name: "Send" }).click();
    await expect(page.getByTestId("answer").last()).toContainText("not established");
  });

  test("chat history persists across reloads", async ({ page }) => {
    await page.goto("/assistant");
    await expect(page.getByTestId("answer").first()).toBeVisible();
    await page.reload();
    await expect(page.getByText("Is dental scaling covered?").first()).toBeVisible();
  });

  test("evidence explorer compares retrieval methods", async ({ page }) => {
    await page.goto("/evidence");
    await page.getByTestId("evidence-query").fill("Anesthesia charges");
    await page.getByRole("button", { name: "Search" }).click();
    await expect(page.getByText("Keyword baseline (BM25)")).toBeVisible();
    await expect(page.getByText("Semantic embeddings")).toBeVisible();
  });

  test("constellation renders real nodes", async ({ page }) => {
    await page.goto("/constellation");
    await expect(page.getByTestId("constellation").locator(".react-flow__node").first()).toBeVisible();
    expect(await page.locator(".react-flow__node").count()).toBeGreaterThan(20);
  });

  test("clause reference opens the source viewer with the highlighted page", async ({ page }) => {
    await page.goto("/claim");
    await page.getByTestId("row-13").click();
    await page.getByRole("button", { name: "Open source of clause 4.3" }).first().click();
    const dialog = page.getByRole("dialog");
    await expect(dialog).toContainText("Comfort and Personal Charges");
    await expect(dialog.getByRole("img", { name: /Page 3/ })).toBeVisible();
    await page.keyboard.press("Escape");
    await expect(dialog).toBeHidden();
  });

  test("command palette navigates", async ({ page }) => {
    await page.goto("/dashboard");
    await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
    await page.keyboard.press("Control+k");
    await page.getByLabel("Search commands").fill("money");
    await page.keyboard.press("Enter");
    await expect(page).toHaveURL(/money-flow/);
  });

  test("fraud & fairness shows the brochure discrepancy with side-by-side evidence", async ({ page }) => {
    await page.goto("/fairness");
    await expect(page.getByTestId("fairness-status")).toContainText("Multiple issues require review");
    await page.getByRole("button", { name: /Room Rent: INR 10,000.00 in the summary/ }).click();
    await expect(page.getByText("But this document says").first()).toBeVisible();
    await expect(page.getByText("Documented restrictive terms")).toBeVisible();
  });

  test("action center drafts a neutral clarification request", async ({ page }) => {
    await page.goto("/actions");
    await expect(page.getByTestId("letter")).toHaveValue(/Request for clarification/);
    await expect(page.getByTestId("letter")).not.toHaveValue(/fraud/i);
    await expect(page.getByTestId("questions").locator("li").first()).toBeVisible();
  });

  test("copilot answers with evidence and working actions", async ({ page }) => {
    await page.goto("/claim");
    await page.getByTestId("row-9").click();
    await page.getByTestId("copilot-launcher").click();
    await page.getByTestId("copilot-input").fill("Explain this in simpler language");
    await page.keyboard.press("Enter");
    await expect(page.getByTestId("copilot-answer").last()).toContainText("MVI Infusion");
    await page.getByRole("button", { name: "Open clause 4.2" }).click();
    await expect(page.getByRole("dialog", { name: /Vitamins and Supplements/ })).toBeVisible();
  });

  test("report downloads are real files and are recorded", async ({ page }) => {
    await page.goto("/reports");
    const [pdf] = await Promise.all([page.waitForEvent("download"), page.getByTestId("download-pdf").click()]);
    expect(pdf.suggestedFilename()).toMatch(/nivaaran-report-.*\.pdf/);
    const head = (await import("node:fs")).readFileSync((await pdf.path())!).subarray(0, 5).toString();
    expect(head).toBe("%PDF-");
    const [js] = await Promise.all([page.waitForEvent("download"), page.getByTestId("download-json").click()]);
    expect(js.suggestedFilename()).toMatch(/\.json$/);
    await page.goto("/dashboard");
    await expect(page.getByText(/^PDF · /).first()).toBeVisible();
  });

  test("bill lines can be corrected; the original extraction is kept and the claim re-analysed", async ({ page }) => {
    await page.goto("/claim");
    await page.getByTestId("edit-bill").click();
    await page.getByLabel("Line 13 amount").fill("1000");
    await page.getByTestId("save-bill").click();
    await expect(page.getByText("Corrected by you").first()).toBeVisible();
    await expect(page.getByText(/Originally extracted: TV & telephone charges/).first()).toBeVisible();
    await expect(page.getByText(/does not equal the stated bill total/).first()).toBeVisible();
    await page.getByTestId("confirm-bill").click();
    await expect(page.getByText(/Lines confirmed by you/)).toBeVisible();
    await page.reload();
    await expect(page.getByText("Corrected by you").first()).toBeVisible();   // persisted on the server
  });

  test("invalid upload shows a useful error", async ({ page }) => {
    await page.goto("/documents");
    await page.getByTestId("doc-upload").setInputFiles({ name: "notes.txt", mimeType: "text/plain", buffer: Buffer.from("hello") });
    await expect(page.getByRole("alert").filter({ hasText: /PDF/ })).toBeVisible();
  });
});

test.describe("Landing and intro", () => {
  test("landing page loads hero and every story section", async ({ page }) => {
    await page.goto("/?nointro");
    await expect(page.getByRole("heading", { level: 1 })).toContainText("Insurance clarity.");
    for (const h of ["Three documents. Three different answers.", "What happens after you upload.", "Where every rupee went.",
      "Not every refusal is unfair. Some deserve a second look.", "Ask why. Get the clause.", "Your documents are yours."]) {
      await expect(page.getByRole("heading", { name: h })).toBeAttached();
    }
  });

  test("cinematic intro plays every time the site is opened, and can be skipped", async ({ page }) => {
    await page.goto("/");
    const skip = page.getByTestId("skip-intro");
    await expect(skip).toBeVisible();
    await skip.click();
    await expect(skip).toBeHidden();
    await expect(page.getByRole("heading", { level: 1 })).toContainText("Insurance clarity.");
    await page.reload();
    await expect(page.getByTestId("skip-intro")).toBeVisible();   // a fresh visit plays it again
    await page.goto("/?nointro");
    await expect(page.getByTestId("skip-intro")).toHaveCount(0);
  });

  test("reduced motion skips the intro", async ({ browser }) => {
    const ctx = await browser.newContext({ reducedMotion: "reduce" });
    const page = await ctx.newPage();
    await page.goto("http://localhost:5173/");
    await expect(page.getByRole("heading", { level: 1 })).toContainText("Insurance clarity.");
    await expect(page.getByTestId("skip-intro")).toHaveCount(0);
    await ctx.close();
  });

  test("hero ask box hands the question to the assistant, which answers it", async ({ page }) => {
    await page.goto("/?nointro");
    await page.getByLabel("Ask Nivaaran about a policy or claim").fill("Why was the room charge reduced?");
    await page.getByRole("button", { name: "Ask", exact: true }).click();
    await expect(page).toHaveURL(/\/assistant/, { timeout: 60_000 });
    await expect(page.getByTestId("answer").last()).toBeVisible({ timeout: 30_000 });
    await expect(page.getByText("Why was the room charge reduced?").last()).toBeVisible();
  });

  test("Analyze a Claim opens an isolated demo workspace without an account", async ({ page }) => {
    await page.goto("/?nointro");
    await page.getByTestId("landing-demo").click();
    await expect(page).toHaveURL(/\/claim/, { timeout: 60_000 });
    await expect(page.getByTestId("ledger")).toBeVisible();
  });
});

test.describe("Policy read-aloud", () => {
  let state = "";
  test.beforeAll(async ({ browser }) => { state = await demoState(browser, "reader"); });
  test.use({ storageState: async ({}, use) => use(state) });

  test("policy summary is available in English, Hindi and Marathi, with clause references", async ({ page }) => {
    await page.goto("/documents");
    const reader = page.getByTestId("policy-reader");
    await expect(reader).toBeVisible();
    await reader.getByTestId("summary-mr").click();
    await expect(reader.getByText("काय कव्हर आहे")).toBeVisible();
    await reader.getByTestId("summary-hi").click();
    await expect(reader.getByText("क्या कवर है")).toBeVisible();
    await reader.getByTestId("summary-en").click();
    await expect(reader.getByText("What is not covered")).toBeVisible();
    await expect(reader.getByRole("button", { name: /Open clause/ }).first()).toBeVisible();
    await expect(reader.getByTestId("play-summary")).toBeEnabled();
    await expect(reader.getByTestId("play-full")).toBeVisible();
  });

  test("assistant answers a Marathi question from the documents", async ({ page }) => {
    await page.goto("/assistant");
    await page.getByRole("button", { name: "माझ्या खोलीचे पूर्ण भाडे मिळेल का?" }).click();
    await expect(page.getByTestId("answer").last()).toContainText("तुमचा प्रश्न असा समजला");
    await expect(page.getByTestId("answer").last()).toContainText("Deluxe Room Charges");
  });
});
