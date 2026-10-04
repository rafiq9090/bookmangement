# Production readiness audit

Date: 2026-10-03

Remediation update: the code findings below have been addressed. See [production-fixes.md](production-fixes.md) for changes, verification, and remaining hosting checks. This report describes the earlier audited state.

Verdict: Not ready for public production. Suitable for continued local development and controlled staging after addressing the security findings.

## Scope and evidence

Reviewed settings, URL routing, authentication, listings, uploads, messaging, pickup services, maps, templates, and deployment documentation. No application code or live inventory was changed during this audit.

- `test apps --keepdb`: 37 tests passed against PostgreSQL, including the simultaneous pickup acceptance test. Redis connection timeouts occurred in legacy checkout tests; those tests passed using database locking.
- `check --deploy` under the default local settings: six warnings for DEBUG, secret strength, HTTPS redirect, HSTS, secure session cookies, and secure CSRF cookies. These are local-environment findings, not proof that production settings lack every protection.
- `check --deploy --settings=config.settings.production`: startup failed because explicit ALLOWED_HOSTS are not configured. Production settings already enable secure cookies, HTTPS redirect, and HSTS.
- `makemigrations --check --dry-run`: no missing migrations.
- Anonymous smoke requests to home, store, authors, login, register, and password reset returned 200. Inbox, pickups, seller listings, and tracking returned expected redirects.
- All project HTML templates compiled successfully.

This audit does not certify a deployed server: no staging domain, TLS endpoint, reverse proxy, browser walkthrough of every flow, SMTP delivery, restore drill, dependency vulnerability scan, or load test was verified. Passing tests do not cover the gaps below.

## Launch blockers

### 1. Unsupported Django version

`requirements/base.txt:1` restricts Django to 5.1; installed version is 5.1.15. Django lists 5.1 as unsupported, with extended support ending December 3, 2025. Upgrade to a supported series and its current security patch; 5.2 LTS is a suitable migration target after checking package compatibility. Lock dependencies and scan the resolved environment.

Source: https://www.djangoproject.com/download/

### 2. Unsafe post-login redirects

`apps/accounts/web_views.py:20` and `apps/accounts/platform_admin_views.py:25` accept arbitrary GET/POST `next` values and redirect to them after authentication. An attacker can craft a login link that sends the user to an external site after sign-in. Validate with Django's `url_has_allowed_host_and_scheme`, restrict to the application's host, and fall back to an internal page. Apply the rule to both login flows and registration.

### 3. Incomplete account protections

`apps/accounts/web_views.py:57` accepts six-character passwords and does not call Django's configured password validators. No application-level login/registration throttling was found. Enforce validators, validate email input server-side, and add throttling for password login, registration, JWT token issuance, and password reset. Configure and verify password-reset email delivery on staging.

`SIMPLE_JWT` enables refresh-token blacklisting, but the blacklist app is absent from INSTALLED_APPS. Ensure revocation and rotation behave as intended and add tests.

### 4. Upload validation and serving

`apps/messaging/views.py:75` and `apps/messaging/web_views.py:329` save uploaded chat files directly, bypassing image-form/serializer validation. Profile avatars and edit-form cover replacements also save raw uploads. Model ImageField assignment alone does not run form validation. Validate content, image dimensions, file sizes, and allowed formats through a common service; enforce body limits at the proxy. Re-encode accepted images and serve uploads safely from a separate media origin. Participant checks on chat endpoints do not make public MEDIA_URL files private.

Private dispute evidence does use separate storage with no public URL; retain that boundary and verify that deployment never serves private_uploads directly.

### 5. Shared catalog edits cross seller boundaries

`apps/listings/web_views.py:443` edits the shared Book title; nearby code replaces authors/categories, and line 495 replaces its cover. A seller who owns one listing can therefore change catalog data used by other sellers' copies of the same book. Separate listing-specific details from canonical catalog data, or restrict catalog edits to moderation. Regression-test two sellers listing the same book.

### 6. Map service policy mismatch

`apps/books/web_views.py:517` implements typeahead suggestions and calls `search_osm_locations`. `apps/books/services/osm_location.py:282` sends these searches to public Nominatim. The public service prohibits autocomplete, limits the aggregate application to one request per second, and requires an identifiable client and attribution. The current service caches results but has no shared aggregate limiter; the default cache is process-local. Debouncing browser input does not solve this.

Use the curated/local database suggestions for autocomplete. If public Nominatim remains for explicit user-submitted searches, add a shared limiter/cache, configurable provider endpoint, an identifying contact, and compliant attribution. Alternatively use an autocomplete-capable provider or self-hosted service. Keep manual district/area and pin input available. Do not send confidential pickup locations to a public service.

Source: https://operations.osmfoundation.org/policies/nominatim/

### 7. Production environment cannot currently start

Production settings reject wildcard ALLOWED_HOSTS in the current environment. Configure explicit domains, a strong unique secret, production settings selection, narrow CSRF trusted origins, trusted proxy headers, and HTTPS. `manage.py` defaults to local settings. Do not deploy the development server.

The included docker-compose file runs PostgreSQL and Redis only; it does not establish the web server, TLS proxy, worker, scheduler, static/media serving, backups, or monitoring. It publishes database and Redis ports on all host interfaces with a default database password. Treat it as local infrastructure; production should use private networking, strong credentials, and restricted access.

## Required before a public launch

1. Replace browser Tailwind compilation in `templates/base.html:11` with generated, versioned CSS. Tailwind explicitly says its Play CDN is for development, not production: https://tailwindcss.com/docs/installation/play-cdn
2. Verify static and public media serving with DEBUG=False. Django's development static/media routes exist only in DEBUG. Separately persist and back up private evidence.
3. Run a worker and reservation-expiry schedule, or a monitored periodic management command. Verify expired copies restock without a participant visiting a page.
4. Finish pickup-only UI cleanup: the footer still advertises Fast Checkout and Delivery & Services; profile and legacy templates retain shipping/payment language. Removed header links alone do not complete this cleanup. Preserve historical records where needed.
5. Add pagination and bounded history for inbox, pickup lists, and seller inventory. Conversation serialization nests message history and inbox polling will need realistic concurrency testing.
6. Validate all submitted fields before database writes, including original MRP and edition year. Test malformed numeric input, author slug collisions, missing photos, and invalid category IDs. Validate cover uploads too.
7. Add status-transition tests across HTML and API endpoints: reserved cancellation, expired reservation cancellation during editing, handover/dispute protection, completed-sale protection, and simultaneous edit/accept actions. The HTML and REST listing editors currently differ on editing sold copies.
8. Verify backup restore, SMTP delivery, error alerting, structured logs, health checks, and moderation access on staging. Test the complete buyer/seller pickup flow on desktop and mobile, plus cross-user access denial and protected evidence downloads.

## Release gate

Launch only after security blockers are fixed, production checks pass with real deployment configuration, the supported dependency set passes tests, the staging buyer/seller flow works, map usage is compliant, uploads are served safely, and backup restoration and scheduled expiry have been demonstrated.
