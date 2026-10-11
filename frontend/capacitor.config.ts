import type { CapacitorConfig } from "@capacitor/cli";

/**
 * Nivaaran for Android (Play Store) and iOS (App Store), built with Capacitor.
 *
 * The app shows the live Nivaaran website inside a native shell, so it is always exactly the same as the site and every
 * update to the site reaches the app without a store release. Set NIVAARAN_APP_URL to the public HTTPS address of the
 * site before building a release, e.g.
 *     set NIVAARAN_APP_URL=https://nivaaran.in && npx cap sync
 * Without it, the app points at this PC for testing (10.0.2.2 is the Android emulator's address for the host machine).
 */
const url = process.env.NIVAARAN_APP_URL || "http://10.0.2.2:8000";
const local = url.startsWith("http://");

const config: CapacitorConfig = {
  appId: "in.nivaaran.app",
  appName: "Nivaaran",
  webDir: "dist",
  server: {
    url,
    cleartext: local,                 // plain http only for local testing; release builds use https
    allowNavigation: [new URL(url).host],
  },
  android: { allowMixedContent: false, captureInput: true },
  ios: { contentInset: "never", scheme: "Nivaaran" },
  plugins: {
    SplashScreen: { launchShowDuration: 1200, backgroundColor: "#142d27", showSpinner: false, androidScaleType: "CENTER_CROP" },
    StatusBar: { style: "DARK", backgroundColor: "#142d27", overlaysWebView: false },
  },
};

export default config;
