/**
 * The installable app (Progressive Web App): registers the service worker in production builds, and keeps the
 * browser's install prompt so the "Install app" button can show it later. Browsers fire that prompt only once,
 * often before React has rendered, so it is captured here at start-up.
 */
interface InstallPrompt extends Event { prompt: () => Promise<void>; userChoice: Promise<{ outcome: "accepted" | "dismissed" }> }

let deferred: InstallPrompt | null = null;
const listeners = new Set<() => void>();
const notify = () => listeners.forEach((f) => f());

export function initPwa() {
  if (typeof window === "undefined") return;
  window.addEventListener("beforeinstallprompt", (e) => { e.preventDefault(); deferred = e as InstallPrompt; notify(); });
  window.addEventListener("appinstalled", () => { deferred = null; notify(); });
  // Only the built site registers it; during development Vite's hot reload must not be cached.
  if (import.meta.env.PROD && "serviceWorker" in navigator) {
    window.addEventListener("load", () => { navigator.serviceWorker.register("/sw.js").catch(() => { /* app still works as a website */ }); });
  }
}

export const onInstallChange = (f: () => void) => { listeners.add(f); return () => { listeners.delete(f); }; };
export const canPromptInstall = () => deferred !== null;

/** Already running as an installed app (opened from the home screen)? */
export const isInstalled = () =>
  typeof window !== "undefined" && (window.matchMedia("(display-mode: standalone)").matches || (navigator as Navigator & { standalone?: boolean }).standalone === true);

/** iPhone/iPad Safari has no install prompt; people add it from the Share menu instead. */
export const isIos = () => typeof navigator !== "undefined" && /iphone|ipad|ipod/i.test(navigator.userAgent) && !/crios|fxios|edgios/i.test(navigator.userAgent);

export async function promptInstall(): Promise<boolean> {
  if (!deferred) return false;
  await deferred.prompt();
  const { outcome } = await deferred.userChoice;
  deferred = null; notify();
  return outcome === "accepted";
}
