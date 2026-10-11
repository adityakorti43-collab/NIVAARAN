// Screenshots every page (desktop and phone) inside a fresh synthetic demo workspace, for visual review.
// Usage: node scripts/snap-pages.mjs <outDir>
import { chromium } from "@playwright/test";
import fs from "node:fs";
import path from "node:path";

const BASE = process.env.NIVAARAN_URL ?? "http://localhost:5173";
const OUT = path.resolve(process.argv[2] ?? "snaps");
fs.mkdirSync(OUT, { recursive: true });
const ROUTES = ["/?nointro", "/login", "/dashboard", "/documents", "/claim", "/evidence", "/constellation", "/money-flow", "/what-if", "/assistant", "/fairness", "/actions", "/costs", "/evaluation", "/reports", "/settings"];

const browser = await chromium.launch({ channel: "chrome" });
for (const [label, viewport, full] of [["desk", { width: 1440, height: 900 }, true], ["phone", { width: 390, height: 844 }, false]]) {
  const ctx = await browser.newContext({ viewport, deviceScaleFactor: 1, reducedMotion: "reduce" });
  await ctx.request.post(BASE + "/api/demo/enter");
  const page = await ctx.newPage();
  const errors = [];
  page.on("pageerror", (e) => errors.push(e.message));
  for (const r of ROUTES) {
    await page.goto(BASE + r);
    await page.waitForLoadState("networkidle").catch(() => {});
    await page.waitForTimeout(1200);
    const name = `${label}-${r.replace(/[/?]/g, "_") || "home"}.png`;
    await page.screenshot({ path: path.join(OUT, name), fullPage: full && r === "/?nointro" ? true : full });
  }
  console.log(label, "errors:", errors.length ? errors : "none");
  await ctx.close();
}
await browser.close();
console.log("saved to", OUT);
