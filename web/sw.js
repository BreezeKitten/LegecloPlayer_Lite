const CACHE_NAME = 'legeclo-pwa-v3';
const CORE_ASSETS = [
  '/lib/spine-player.js',
  '/manifest.json',
  '/icons/icon-192.png',
  '/icons/icon-512.png',
  '/icons/apple-touch-icon.png'
];

self.addEventListener('install', (e) => {
  e.waitUntil(
    caches.open(CACHE_NAME).then((cache) => {
      return cache.addAll(CORE_ASSETS).catch(err => {
        console.warn('Pre-cache core assets notice:', err);
      });
    }).then(() => self.skipWaiting())
  );
});

self.addEventListener('activate', (e) => {
  e.waitUntil(
    caches.keys().then((keys) => {
      return Promise.all(
        keys.map((k) => {
          if (k !== CACHE_NAME) return caches.delete(k);
        })
      );
    }).then(() => self.clients.claim())
  );
});

// Network-first for code & API, fallback to cache
self.addEventListener('fetch', (e) => {
  const url = new URL(e.request.url);

  // Bypass service worker for Range requests (streaming video/audio) and dynamic APIs
  if (e.request.headers.has('range') || url.pathname.startsWith('/api/') || url.pathname.startsWith('/cache/')) {
    return;
  }

  // Network-first for app code (HTML, JS, CSS)
  if (url.pathname.endsWith('.js') || url.pathname.endsWith('.css') || url.pathname === '/' || url.pathname.endsWith('.html')) {
    e.respondWith(
      fetch(e.request).then((res) => {
        const clone = res.clone();
        caches.open(CACHE_NAME).then((c) => c.put(e.request, clone));
        return res;
      }).catch(() => caches.match(e.request))
    );
    return;
  }

  e.respondWith(
    caches.match(e.request).then((cached) => {
      return cached || fetch(e.request);
    })
  );
});
