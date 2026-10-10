// Records a narrated-free video walkthrough of Nivaaran (intro → landing → ask box → workspace pages).
// Usage: node scripts/record-tour.mjs   (expects the web app on :5173 and the API on :8000)
// Output: frontend/video/nivaaran-tour.webm
import { chromium } from "@playwright/test";
import fs from "node:fs";
import path from "node:path";

const BASE = process.env.NIVAARAN_URL ?? "http://localhost:5173";
const OUT = path.resolve("video");
fs.mkdirSync(OUT, { recursive: true });

const browser = await chromium.launch({ channel: "chrome" });
const ctx = await browser.newContext({ viewport: { width: 1440, height: 900 }, recordVideo: { dir: OUT, size: { width: 1440, height: 900 } } });
const page = await ctx.newPage();
const pause = (ms) => page.waitForTimeout(ms);

async function smoothScroll(total, steps = 40, delay = 60) {
  for (let i = 0; i < steps; i++) { await page.mouse.wheel(0, total / steps); await pause(delay); }
}

// 1. Cinematic intro, then the landing hero with the 3D receipt
await page.goto(BASE + "/");
await pause(9000);
const skip = page.getByTestId("skip-intro");
if (await skip.isVisible().catch(() => false)) await skip.click();
await pause(3500);
await page.mouse.move(1000, 400, { steps: 25 }); await pause(800);
await page.mouse.move(1150, 600, { steps: 25 }); await pause(1200);

// 2. Scroll the story sections
await smoothScroll(5200, 120, 70);
await pause(1200);
await page.evaluate(() => window.scrollTo({ top: 0, behavior: "smooth" }));
await pause(2000);

// 3. Ask a question from the hero; it opens a private demo workspace and answers there
const ask = page.getByLabel("Ask Nivaaran about a policy or claim");
await ask.click();
await ask.pressSequentially("Why was the room charge reduced?", { delay: 55 });
await pause(600);
await page.getByRole("button", { name: "Ask", exact: true }).click();
await page.waitForURL(/\/assistant/, { timeout: 60_000 });
await page.getByTestId("answer").last().waitFor({ timeout: 30_000 });
await pause(4000);

// 4. Tour the workspace
for (const [route, scroll] of [["/dashboard", 600], ["/claim", 1400], ["/money-flow", 500], ["/constellation", 0], ["/fairness", 700], ["/actions", 600], ["/what-if", 400]]) {
  await page.goto(BASE + route);
  await pause(2800);
  if (scroll) { await smoothScroll(scroll, 30, 60); await pause(1500); }
}

// 5. Copilot
await page.getByTestId("copilot-launcher").click();
await pause(3000);

await ctx.close();
const video = page.video();
const final = path.join(OUT, "nivaaran-tour.webm");
if (video) { fs.renameSync(await video.path(), final); console.log("saved", final); }
await browser.close();
