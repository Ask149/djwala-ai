// DjwalaAI Service Worker — minimal, for PWA installability + asset caching
const CACHE_NAME = 'djwala-v16';
const SHELL_ASSETS = [
    '/',
    '/static/css/style.css?v=16',
    '/static/js/mix-engine.js?v=16',
    '/static/js/app.js?v=16',
    '/static/icons/icon.svg',
];

self.addEventListener('install', (event) => {
    event.waitUntil(
        caches.open(CACHE_NAME)
            .then(cache => cache.addAll(SHELL_ASSETS))
            .then(() => self.skipWaiting())
    );
});

self.addEventListener('activate', (event) => {
    event.waitUntil(
        caches.keys().then(keys =>
            Promise.all(keys.filter(k => k !== CACHE_NAME).map(k => caches.delete(k)))
        ).then(() => self.clients.claim())
    );
});

self.addEventListener('fetch', (event) => {
    const url = new URL(event.request.url);

    // Don't cache API calls, WebSocket, analytics, YouTube, or external requests
    if (url.pathname.startsWith('/session') ||
        url.pathname.startsWith('/api/') ||
        url.pathname.startsWith('/analytics') ||
        url.pathname.startsWith('/health') ||
        url.origin !== self.location.origin) {
        return; // Let the browser handle it normally
    }

    // Network-first for app shell assets
    event.respondWith(
        fetch(event.request)
            .then(response => {
                // Cache successful responses
                if (response.ok) {
                    const clone = response.clone();
                    caches.open(CACHE_NAME).then(cache => cache.put(event.request, clone));
                }
                return response;
            })
            .catch(() => caches.match(event.request))
    );
});
