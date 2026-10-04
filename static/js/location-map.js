/* Public map coordinates are rounded to area scale; no geocoding API needed. */
(() => {
  if (!window.L) return;
  const attribution = '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors';
  function makeMap(element, lat, lon) {
    const map = L.map(element).setView([lat, lon], 12);
    L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png', {attribution, maxZoom: 19}).addTo(map);
    return map;
  }
  document.querySelectorAll('[data-location-picker]').forEach(element => {
    const parent = element.parentElement;
    const lat = parent.querySelector('[data-location-lat]');
    const lon = parent.querySelector('[data-location-lon]');
    const map = makeMap(element, Number(lat.value || 23.81), Number(lon.value || 90.41));
    let marker = lat.value && lon.value ? L.marker([Number(lat.value), Number(lon.value)]).addTo(map) : null;
    map.on('click', event => {
      const precision = element.dataset.locationPrecision === '6' ? 6 : 2;
      lat.value = event.latlng.lat.toFixed(precision);
      lon.value = event.latlng.lng.toFixed(precision);
      const point = [Number(lat.value), Number(lon.value)];
      if (marker) marker.setLatLng(point); else marker = L.marker(point).addTo(map);
    });
  });
  document.querySelectorAll('[data-public-map]').forEach(element => {
    const lat = Number(element.dataset.lat), lon = Number(element.dataset.lon);
    if (Number.isFinite(lat) && Number.isFinite(lon)) {
      const map = makeMap(element, lat, lon);
      L.circle([lat, lon], {radius: 1000}).addTo(map);
    }
  });
})();
