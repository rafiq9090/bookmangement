# Responsive presentation

Templates share content, form actions, and permissions across screen sizes.
Avoid duplicating Django views or forms to implement visual changes.

- `static/css/desktop-view.css`: desktop presentation, loaded at 768px and wider.
- `static/css/tablet-view.css`: tablet overrides for 768–1023px.
- `static/css/mobile-theme.css`: shared phone colors, surfaces, controls and focus states.
- `static/css/mobile-app.css`: mobile presentation, loaded below 768px. Contains
  shared mobile primitives followed by page and component overrides.
- `static/css/custom.css` and compiled `tailwind.css`: shared component styling.
- `templates/components/mobile_navigation.html`: phone navigation.
- `static/css/mobile-admin.css`: operations pages, retaining their sidebar drawer.

The base template supplies `body[data-page]` from the resolved URL name. Use this
for page-specific rules; use explicit component classes for reusable layouts.
Keep mobile overrides in the mobile stylesheet. Preserve form field names,
CSRF tokens, element IDs referenced by JavaScript, and server-side validation.

After changing templates, run `npm run build:css` and `scripts/django.ps1 check`.
Check 360px, 390px, 767px, 768px and desktop widths for overflow, keyboard use,
long content, and controls hidden behind fixed navigation.
