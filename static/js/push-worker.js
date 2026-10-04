self.addEventListener('push', event => {
  let data = {};
  try { data = event.data?.json() || {}; } catch (_) { /* Generic fallback. */ }
  const url = new URL(data.url || '/pickups/', self.location.origin);
  event.waitUntil(self.registration.showNotification(data.title || 'Book ReSeller', {
    body: data.body || 'You have a new marketplace update.',
    tag: data.tag || 'marketplace-update',
    data: { url: url.origin === self.location.origin ? url.href : self.location.origin + '/pickups/' }
  }));
});
self.addEventListener('notificationclick', event => {
  event.notification.close();
  const url = new URL(event.notification.data.url, self.location.origin);
  if (url.origin !== self.location.origin) return;
  event.waitUntil(clients.matchAll({ type: 'window', includeUncontrolled: true }).then(async windows => {
    for (const client of windows) {
      if (client.url === url.href && 'focus' in client) return client.focus();
    }
    return clients.openWindow(url.href);
  }));
});
