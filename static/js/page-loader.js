/* Navigation feedback shared by desktop and mobile. Does not block interaction. */
(() => {
  const loader = document.getElementById('pageLoader');
  if (!loader) return;
  let pending;
  let expiry;
  function clear() {
    clearTimeout(pending);
    clearTimeout(expiry);
    loader.hidden = true;
  }
  function start() {
    clear();
    pending = setTimeout(() => {
      loader.hidden = false;
      // A cancelled download/navigation must never leave permanent feedback.
      expiry = setTimeout(clear, 15000);
    }, 120);
  }
  document.addEventListener('click', event => {
    if (event.button !== 0 || event.ctrlKey || event.metaKey || event.shiftKey || event.altKey) return;
    const link = event.target.closest('a[href]');
    if (!link || link.hasAttribute('download') || (link.target && link.target !== '_self')) return;
    const destination = new URL(link.href, location.href);
    if (destination.origin !== location.origin || !['http:', 'https:'].includes(destination.protocol)) return;
    if (destination.pathname === location.pathname && destination.search === location.search) return;
    queueMicrotask(() => { if (!event.defaultPrevented) start(); });
  });
  document.addEventListener('submit', event => {
    const form = event.target;
    const target = event.submitter?.formTarget || form.target;
    if (target && target !== '_self') return;
    queueMicrotask(() => { if (!event.defaultPrevented) start(); });
  });
  window.addEventListener('pageshow', clear);
  window.addEventListener('pagehide', clear);
  window.addEventListener('popstate', clear);
})();
