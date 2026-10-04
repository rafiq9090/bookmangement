(() => {
  const button = document.getElementById('pushToggle');
  const status = document.getElementById('pushStatus');
  if (!button) return;
  const csrf = document.querySelector('[name=csrfmiddlewaretoken]')?.value;
  let registration;
  let config;
  let subscription;
  async function save(data) {
    const response = await fetch('/notifications/push/subscription/', {
      method: 'POST', credentials: 'same-origin',
      headers: {'Content-Type': 'application/json', 'X-CSRFToken': csrf},
      body: JSON.stringify(data)
    });
    if (!response.ok) throw new Error('Unable to save notification settings. Try again.');
  }
  function refresh() {
    button.textContent = subscription ? 'Disable notifications' : 'Enable notifications';
    status.textContent = subscription ? 'Notifications are enabled on this device.' : 'Get alerts for messages and pickup updates on this device.';
  }
  async function setup() {
    if (!window.isSecureContext || !('serviceWorker' in navigator) || !('PushManager' in window) || !('Notification' in window)) {
      status.textContent = 'Push notifications are unavailable in this browser. On iPhone, add this website to your Home Screen first.';
      return;
    }
    const response = await fetch('/notifications/push/config/');
    if (!response.ok) throw new Error('Please sign in again to manage notifications.');
    config = await response.json();
    if (!config.enabled) { status.textContent = 'Push notifications will be available after server setup.'; return; }
    registration = await navigator.serviceWorker.register('/push-worker.js');
    await navigator.serviceWorker.ready;
    subscription = await registration.pushManager.getSubscription();
    if (subscription) await save(subscription.toJSON());
    refresh();
    button.hidden = false;
  }
  button.addEventListener('click', async () => {
    button.disabled = true;
    try {
      if (subscription) {
        await save({endpoint: subscription.endpoint, unsubscribe: true});
        await subscription.unsubscribe();
        subscription = null;
      } else {
        const permission = await Notification.requestPermission();
        if (permission !== 'granted') throw new Error('Notifications are blocked. Allow them in your browser settings to enable alerts.');
        const key = config.publicKey.replace(/-/g, '+').replace(/_/g, '/');
        const bytes = Uint8Array.from(atob(key + '='.repeat((4 - key.length % 4) % 4)), c => c.charCodeAt(0));
        subscription = await registration.pushManager.subscribe({userVisibleOnly: true, applicationServerKey: bytes});
        try { await save(subscription.toJSON()); }
        catch (error) { await subscription.unsubscribe(); subscription = null; throw error; }
      }
      refresh();
    } catch (error) { status.textContent = error.message; }
    finally { button.disabled = false; }
  });
  setup().catch(() => { status.textContent = 'Unable to load notification settings. Refresh to try again.'; });
})();
