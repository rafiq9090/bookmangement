/* Inbox interactions: safe DOM rendering, search, attachments and live updates. */
(() => {
  const stream = document.getElementById('chatStream');
  const convId = Number(stream?.dataset.convId || 0);
  const api = convId ? `/inbox/${convId}/api/messages/` : null;
  let lastId = Number(stream?.dataset.lastId || 0);
  let filter = 'all';
  const error = document.getElementById('chatError');
  const form = document.getElementById('chatForm');
  const input = document.getElementById('chatTextInput');
  const photo = document.getElementById('photoInput');
  function showError(message) { if (error) { error.textContent = message; error.hidden = !message; } }
  function clearAttachment() { if (photo) photo.value = ''; const preview = document.getElementById('attachmentIndicator'); if (preview) preview.hidden = true; }
  function applySearch() {
    const query = document.getElementById('conversationSearch').value.trim().toLowerCase();
    let visible = 0;
    document.querySelectorAll('.conversation-row').forEach(row => {
      row.hidden = !row.dataset.search.toLowerCase().includes(query) || (filter === 'unread' && Number(row.dataset.unread) === 0);
      if (!row.hidden) visible++;
    });
    document.getElementById('searchEmpty').hidden = visible !== 0;
  }
  document.getElementById('conversationSearch')?.addEventListener('input', applySearch);
  document.querySelectorAll('[data-filter]').forEach(button => button.addEventListener('click', () => {
    filter = button.dataset.filter;
    document.querySelectorAll('[data-filter]').forEach(item => item.classList.toggle('is-active', item === button));
    applySearch();
  }));
  document.getElementById('backToConversations')?.addEventListener('click', () => document.getElementById('messenger').classList.remove('is-chat-open'));
  document.getElementById('chatDetailsToggle')?.addEventListener('click', event => {
    const button = event.currentTarget, details = document.getElementById('chatDetails');
    details.hidden = !details.hidden;
    button.setAttribute('aria-expanded', String(!details.hidden));
  });
  photo?.addEventListener('change', () => {
    const preview = document.getElementById('attachmentIndicator');
    document.getElementById('attachmentFileName').textContent = photo.files[0]?.name || '';
    preview.hidden = !photo.files.length;
  });
  document.getElementById('clearAttachment')?.addEventListener('click', clearAttachment);
  function node(tag, className, text) { const element = document.createElement(tag); element.className = className; if (text !== undefined) element.textContent = text; return element; }
  function appendMessage(msg, advanceCursor = true) {
    if (advanceCursor) lastId = Math.max(lastId, Number(msg.id));
    if (!stream || stream.querySelector(`[data-msg-id="${Number(msg.id)}"]`)) return;
    const nearBottom = stream.scrollHeight - stream.scrollTop - stream.clientHeight < 120;
    stream.querySelector('.chat-empty')?.remove();
    const row = node('div', `message-row${msg.is_me ? ' is-outgoing' : ''}`);
    row.dataset.msgId = msg.id;
    const avatar = node('div', `message-avatar chat-avatar ${msg.is_me ? 'avatar-blue' : 'avatar-mint'}`, msg.sender_initial);
    const body = node('div', 'message-body');
    const bubble = node('div', 'message-bubble');
    if (msg.photo_url) {
      const url = new URL(msg.photo_url, window.location.origin);
      const mediaOrigin = new URL(stream.dataset.mediaUrl || '/media/', window.location.origin).origin;
      if ([window.location.origin, mediaOrigin].includes(url.origin) && ['http:', 'https:'].includes(url.protocol)) {
        const image = node('img', 'message-photo'); image.src = url.href; image.alt = 'Shared book photo'; bubble.append(image);
      }
    }
    if (msg.text) bubble.append(node('p', '', msg.text));
    body.append(bubble, node('time', 'message-time', msg.created_at_time));
    row.append(avatar, body); stream.append(row);
    if (msg.is_me || nearBottom) stream.scrollTop = stream.scrollHeight;
  }
  let polling = false;
  async function pollMessages() {
    if (!api || document.hidden || polling) return;
    polling = true;
    try { const response = await fetch(`${api}?after_id=${lastId}`); if (!response.ok) return; const data = await response.json(); (data.messages || []).forEach(msg => appendMessage(msg)); }
    catch (_) { /* Next poll can recover from connection loss. */ }
    finally { polling = false; }
  }
  form?.addEventListener('submit', async event => {
    event.preventDefault();
    if (!input.value.trim() && !photo.files.length) return;
    const button = document.getElementById('chatSubmitBtn'); button.disabled = true; showError('');
    try {
      const response = await fetch(api, {method:'POST', headers:{'X-CSRFToken': form.querySelector('[name=csrfmiddlewaretoken]').value}, body:new FormData(form)});
      const data = await response.json();
      if (!response.ok || !data.success) throw new Error(data.error || 'Message could not be sent. Please try again.');
      appendMessage(data.message, false); input.value = ''; clearAttachment();
    } catch (err) { showError(err.message || 'Connection lost. Your message is still here; try again.'); }
    finally { button.disabled = false; input.focus(); }
  });
  async function updateThreads() {
    if (document.hidden) return;
    try {
      const response = await fetch('/inbox/api/threads/?page=' + encodeURIComponent(new URLSearchParams(window.location.search).get('page') || '1')); if (!response.ok) return;
      const data = await response.json();
      (data.threads || []).forEach(thread => {
        const row = document.querySelector(`[data-conv-id="${Number(thread.id)}"].conversation-row`);
        if (!row) return;
        row.dataset.unread = thread.id === convId ? 0 : thread.unread_count;
        const badge = document.getElementById(`sidebar-unread-${thread.id}`);
        badge.textContent = row.dataset.unread; badge.classList.toggle('is-hidden', Number(row.dataset.unread) === 0);
        const preview = document.getElementById(`sidebar-lastmsg-${thread.id}`);
        if (thread.last_message) preview.textContent = thread.last_message;
      });
      applySearch();
      window.setUnreadMessagesBadgeCount?.(data.unread_count);
    } catch (_) { /* Keep current sidebar on connection loss. */ }
  }
  if (stream) stream.scrollTop = stream.scrollHeight;
  if (api) setInterval(pollMessages, 3000);
  setInterval(updateThreads, 6000);
})();
