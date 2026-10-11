/* Nivaaran service worker: makes the installed app open instantly and fail gracefully offline.
 *
 * - Your data is never cached here: every /api/ request goes straight to the server.
 * - Built files (/assets/*, which have content hashes in their names), icons and fonts are cached after first use.
 * - Pages are fetched fresh from the network; if there is no connection, a friendly offline page is shown.
 */
const VERSION = "nivaaran-v1";
const SHELL = ["/offline.html", "/icons/icon-192.png", "/icons/icon-512.png", "/manifest.webmanifest", "/logo-mark-64.png"];

self.addEventListener("install", (event) => {
  event.waitUntil(caches.open(VERSION).then((c) => c.addAll(SHELL)).then(() => self.skipWaiting()));
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys().then((keys) => Promise.all(keys.filter((k) => k !== VERSION).map((k) => caches.delete(k)))).then(() => self.clients.claim()),
  );
});

async function cacheFirst(request) {
  const cache = await caches.open(VERSION);
  const hit = await cache.match(request);
  if (hit) return hit;
  const res = await fetch(request);
  if (res.ok && (res.type === "basic" || res.type === "cors")) cache.put(request, res.clone());
  return res;
}

self.addEventListener("fetch", (event) => {
  const req = event.request;
  if (req.method !== "GET") return;                                   // uploads, sign-in, edits: network only
  const url = new URL(req.url);
  if (url.origin === self.location.origin && url.pathname.startsWith("/api/")) return;   // your data: never cached
  if (req.mode === "navigate") {
    event.respondWith(fetch(req).catch(async () => (await caches.match("/offline.html")) || Response.error()));
    return;
  }
  const sameOriginStatic = url.origin === self.location.origin &&
    (url.pathname.startsWith("/assets/") || url.pathname.startsWith("/icons/") || /\.(png|svg|webp|woff2?)$/.test(url.pathname));
  const fonts = url.hostname === "fonts.googleapis.com" || url.hostname === "fonts.gstatic.com";
  if (sameOriginStatic || fonts) event.respondWith(cacheFirst(req));
});
