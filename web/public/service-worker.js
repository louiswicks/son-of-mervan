/* Son of Mervan — Service Worker
 * cache-first for static assets, network-first for cross-origin API calls
 */

const CACHE_VERSION = 'v1';
const STATIC_CACHE = `syitb-static-${CACHE_VERSION}`;
const DYNAMIC_CACHE = `syitb-dynamic-${CACHE_VERSION}`;

// Pre-cache the app shell on install
self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(STATIC_CACHE)
      .then((cache) => cache.add('/index.html'))
      .then(() => self.skipWaiting())
  );
});

// Remove stale caches on activate
self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys()
      .then((names) =>
        Promise.all(
          names
            .filter((n) => n !== STATIC_CACHE && n !== DYNAMIC_CACHE)
            .map((n) => caches.delete(n))
        )
      )
      .then(() => self.clients.claim())
  );
});

self.addEventListener('fetch', (event) => {
  const { request } = event;

  // Only intercept GET requests
  if (request.method !== 'GET') return;

  const url = new URL(request.url);

  // Cross-origin (API server, CDN): network-first with cache fallback
  if (url.origin !== self.location.origin) {
    event.respondWith(networkFirst(request));
    return;
  }

  // Navigation requests: serve cached index.html for SPA offline support
  if (request.mode === 'navigate') {
    event.respondWith(
      caches
        .match('/index.html')
        .then((cached) => cached || fetch(request))
        .catch(() => caches.match('/index.html'))
    );
    return;
  }

  // Same-origin static assets: cache-first
  event.respondWith(cacheFirst(request));
});

async function cacheFirst(request) {
  const cached = await caches.match(request);
  if (cached) return cached;

  try {
    const response = await fetch(request);
    if (response.ok) {
      const cache = await caches.open(DYNAMIC_CACHE);
      cache.put(request, response.clone());
    }
    return response;
  } catch {
    // Return whatever is cached, or a basic error response
    return (await caches.match(request)) || Response.error();
  }
}

async function networkFirst(request) {
  try {
    const response = await fetch(request);
    if (response.ok) {
      const cache = await caches.open(DYNAMIC_CACHE);
      cache.put(request, response.clone());
    }
    return response;
  } catch {
    const cached = await caches.match(request);
    return cached || Response.error();
  }
}
