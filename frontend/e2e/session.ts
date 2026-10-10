import { expect, type Browser } from "@playwright/test";
import os from "node:os";
import path from "node:path";

/** A signed-in, isolated synthetic demo workspace, created through the real /api/demo/enter endpoint. */
export async function demoState(browser: Browser, name: string): Promise<string> {
  const file = path.join(os.tmpdir(), `nivaaran-e2e-${name}-${process.pid}.json`);
  const ctx = await browser.newContext({ baseURL: "http://localhost:5173" });
  const r = await ctx.request.post("/api/demo/enter");
  expect(r.ok()).toBeTruthy();
  // Mark the intro as seen so workspace tests start on the page they visit.
  await ctx.addInitScript(() => { try { localStorage.setItem("nivaaran.introSeen.v2", "1"); } catch { /* ignore */ } });
  const page = await ctx.newPage();
  await page.goto("/?nointro");
  await page.evaluate(() => localStorage.setItem("nivaaran.introSeen.v2", "1"));
  await ctx.storageState({ path: file });
  await ctx.close();
  return file;
}
