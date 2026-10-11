/**
 * Behaviour that only applies inside the Android/iOS app (Capacitor). On the website none of this runs.
 *
 *  - Google sign-in opens in the phone's browser (Google refuses to sign in inside app web views); when it finishes, the
 *    server sends the browser to `in.nivaaran.app://auth?token=…`, the phone reopens the app, and the app opens the
 *    single-use sign-in link inside itself, which signs it in.
 *  - The Android back button goes back a page, and leaves the app only from the first page.
 */
import { Capacitor } from "@capacitor/core";

export const isNativeApp = () => Capacitor.isNativePlatform();

export async function openGoogleSignIn(next: string, link = false) {
  const { Browser } = await import("@capacitor/browser");
  const q = new URLSearchParams({ next, app: "1", ...(link ? { link: "1" } : {}) });
  await Browser.open({ url: `${window.location.origin}/api/auth/google/start?${q}`, presentationStyle: "popover" });
}

export async function initNative() {
  if (!isNativeApp()) return;
  const { App } = await import("@capacitor/app");
  const { Browser } = await import("@capacitor/browser");
  App.addListener("appUrlOpen", ({ url }) => {
    let u: URL;
    try { u = new URL(url); } catch { return; }
    if (u.host !== "auth" && u.pathname.replace(/^\/+/, "") !== "auth") return;
    void Browser.close().catch(() => {});
    const token = u.searchParams.get("token");
    const next = u.searchParams.get("next") || "/dashboard";
    window.location.href = token
      ? `/api/auth/login-link?${new URLSearchParams({ token, next })}`
      : next.startsWith("/") ? next : "/dashboard";
  });
  App.addListener("backButton", ({ canGoBack }) => {
    if (canGoBack && window.history.length > 1) window.history.back();
    else void App.exitApp();
  });
}
