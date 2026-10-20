/* Service worker „Przepisy budowlane”.
 * Zasada: awaria nie udaje świeżości. Zapamiętujemy tylko zasoby statyczne (fonty, ikony, style, skrypty
 * aplikacji) i stronę offline. Strony z przepisami i odpowiedzi API zawsze pobieramy z sieci — bez sieci
 * pokazujemy stronę „Brak połączenia”, a nie starą wersję przepisu.
 */
const CACHE = "pb-static-v2";
// Strona offline jest statyczna (bez JavaScriptu): podana pod dowolnym adresem nie wywołuje hydratacji aplikacji.
const OFFLINE = "/offline.html";
const PRECACHE = [
  OFFLINE,
  "/favicon.svg",
  "/manifest.webmanifest",
  "/brand/znak-kolor.svg",
  "/brand/logo-poziome-kolor.svg",
  "/fonts/PBSans-Regular.woff2",
  "/fonts/PBSans-SemiBold.woff2",
  "/fonts/PBSerif-Regular.woff2",
  "/fonts/PBMono-Regular.woff2",
];

self.addEventListener("install", (event) => {
  event.waitUntil(caches.open(CACHE).then((c) => c.addAll(PRECACHE)).then(() => self.skipWaiting()));
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches
      .keys()
      .then((keys) => Promise.all(keys.filter((k) => k !== CACHE).map((k) => caches.delete(k))))
      .then(() => self.clients.claim()),
  );
});

function isStatic(url) {
  return (
    url.origin === self.location.origin &&
    (url.pathname.startsWith("/_next/static/") ||
      url.pathname.startsWith("/fonts/") ||
      url.pathname.startsWith("/icons/") ||
      url.pathname.startsWith("/brand/") ||
      url.pathname === "/favicon.svg")
  );
}

self.addEventListener("fetch", (event) => {
  const req = event.request;
  if (req.method !== "GET") return;
  const url = new URL(req.url);
  if (req.mode === "navigate") {
    event.respondWith(
      fetch(req).catch(async () => {
        const page = await caches.match(OFFLINE, { ignoreVary: true });
        return page ?? new Response("Brak połączenia.", { status: 503, headers: { "Content-Type": "text/plain; charset=utf-8" } });
      }),
    );
    return;
  }
  if (isStatic(url)) {
    event.respondWith(
      caches.match(req).then(
        (hit) =>
          hit ||
          fetch(req).then((res) => {
            if (res.ok) {
              const copy = res.clone();
              caches.open(CACHE).then((c) => c.put(req, copy));
            }
            return res;
          }),
      ),
    );
  }
  // Wszystko inne (API, dane stron) — prosto z sieci, bez pamięci podręcznej.
});
