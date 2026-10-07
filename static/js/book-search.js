document.addEventListener('DOMContentLoaded', () => {
  const input = document.getElementById('storeBookSearch');
  if (!input) return;
  const wrapper = input.parentElement;
  const menu = document.createElement('div');
  menu.id = 'storeBookSuggestions';
  menu.className = 'book-search-suggestions';
  menu.setAttribute('role', 'listbox');
  menu.setAttribute('aria-label', 'Search suggestions');
  menu.hidden = true;
  wrapper.appendChild(menu);
  let timer, controller, active = -1, results = [], version = 0;
  function close() {
    menu.hidden = true;
    input.setAttribute('aria-expanded', 'false');
    input.removeAttribute('aria-activedescendant');
    active = -1;
  }
  function choose(index) {
    input.value = results[index].value;
    close();
    input.form.requestSubmit();
  }
  function highlight() {
    [...menu.children].forEach((button, index) => button.setAttribute('aria-selected', String(index === active)));
    if (active >= 0) {
      input.setAttribute('aria-activedescendant', menu.children[active].id);
      menu.children[active].scrollIntoView({block: 'nearest'});
    }
  }
  input.addEventListener('input', () => {
    clearTimeout(timer);
    if (controller) controller.abort();
    const current = ++version;
    close();
    const query = input.value.trim();
    if (query.length < 2) return;
    timer = setTimeout(async () => {
      controller = new AbortController();
      try {
        const response = await fetch(input.dataset.suggestionsUrl + '?q=' + encodeURIComponent(query), {signal: controller.signal});
        if (!response.ok) return;
        const data = await response.json();
        if (current !== version) return;
        results = data.suggestions || [];
        menu.replaceChildren();
        results.forEach((item, index) => {
          const button = document.createElement('button');
          button.type = 'button';
          button.id = 'book-suggestion-' + index;
          button.setAttribute('role', 'option');
          button.setAttribute('aria-selected', 'false');
          const title = document.createElement('strong');
          title.textContent = item.label;
          const detail = document.createElement('span');
          detail.textContent = item.kind + (item.detail ? ' · ' + item.detail : '');
          button.append(title, detail);
          button.addEventListener('click', () => choose(index));
          menu.appendChild(button);
        });
        menu.hidden = !results.length;
        input.setAttribute('aria-expanded', String(Boolean(results.length)));
      } catch (error) {
        if (error.name !== 'AbortError' && current === version) close();
      }
    }, 250);
  });
  input.addEventListener('keydown', event => {
    if (event.key === 'Escape') {
      ++version;
      clearTimeout(timer);
      if (controller) controller.abort();
      close();
      return;
    }
    if (menu.hidden) return;
    if (event.key === 'ArrowDown' || event.key === 'ArrowUp') {
      event.preventDefault();
      active = event.key === 'ArrowDown' ? (active + 1) % results.length : (active <= 0 ? results.length - 1 : active - 1);
      highlight();
    } else if (event.key === 'Enter' && active >= 0) {
      event.preventDefault();
      choose(active);
    }
  });
  document.addEventListener('click', event => {
    if (!wrapper.contains(event.target)) {
      ++version;
      clearTimeout(timer);
      if (controller) controller.abort();
      close();
    }
  });
});
