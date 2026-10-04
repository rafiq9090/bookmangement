/* Optional motion: content remains visible if JavaScript is unavailable. */
(() => {
  const preference = window.matchMedia('(prefers-reduced-motion: reduce)');
  if (preference.matches || !('IntersectionObserver' in window)) return;
  const observer = new IntersectionObserver(entries => {
    entries.forEach(entry => {
      if (!entry.isIntersecting) return;
      if (!preference.matches) entry.target.classList.add('motion-enter');
      observer.unobserve(entry.target);
    });
  }, { threshold: 0.08 });
  document.querySelectorAll('main > section, .mobile-home-layout > section, .mobile-profile-page > .grid').forEach(section => {
    if (!section.matches('.messenger-page') && !section.querySelector('form, .messenger')) observer.observe(section);
  });
  preference.addEventListener('change', () => {
    if (preference.matches) observer.disconnect();
  });
})();
