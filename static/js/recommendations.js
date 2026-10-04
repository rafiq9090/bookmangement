document.querySelectorAll('[data-recommendation-action]').forEach(button => {
  button.addEventListener('click', async () => {
    const status = button.closest('.recommendation-controls').querySelector('[data-recommendation-status]');
    button.disabled = true;
    try {
      let data = {};
      const action = button.dataset.recommendationAction;
      if (action === 'location') {
        if (!navigator.geolocation) throw new Error('Location is unavailable. You can enter an area in the Store.');
        status.textContent = 'Finding your location…';
        const position = await new Promise((resolve, reject) => navigator.geolocation.getCurrentPosition(resolve, reject, {timeout: 10000, maximumAge: 300000}));
        data = {lat: position.coords.latitude, lon: position.coords.longitude};
      } else data[action] = true;
      const response = await fetch('/recommendations/preferences/', {method: 'POST', credentials: 'same-origin', headers: {'Content-Type': 'application/json', 'X-CSRFToken': button.closest('.recommendation-controls').querySelector('[name=csrfmiddlewaretoken]').value}, body: JSON.stringify(data)});
      if (!response.ok) throw new Error('Could not update preferences. Try again.');
      location.reload();
    } catch (error) { status.textContent = error.code === 1 ? 'Location was not allowed. You can still browse all books.' : (error.message || 'Location is unavailable.'); }
    finally { button.disabled = false; }
  });
});
