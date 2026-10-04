(() => {
  const panel = document.getElementById('cookiePreferences');
  const form = document.getElementById('cookiePreferencesForm');
  const opener = document.getElementById('openCookiePreferences');
  if (!form) return;
  opener.addEventListener('click', () => {
    panel.hidden = !panel.hidden;
    if (!panel.hidden) panel.querySelector('button').focus();
  });
  form.addEventListener('submit', async event => {
    event.preventDefault();
    const data = new FormData(form);
    data.set('personalization', event.submitter.value);
    const buttons = form.querySelectorAll('button');
    buttons.forEach(button => button.disabled = true);
    try {
      const response = await fetch(form.action, {method: 'POST', body: data, credentials: 'same-origin'});
      if (!response.ok) throw new Error();
      panel.hidden = true;
      opener.focus();
    } catch (_) { document.getElementById('cookiePreferencesStatus').textContent = 'Could not save preferences. Please try again.'; }
    finally { buttons.forEach(button => button.disabled = false); }
  });
})();
