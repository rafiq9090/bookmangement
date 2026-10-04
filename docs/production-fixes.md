# Production audit fixes

Implemented on 2026-10-03. This supersedes the code findings in the earlier audit; the original report remains as historical evidence.

## Fixed

- Upgraded Django to 5.2.17, installed the resolved production dependency set, and committed an exact Python package lock. Python dependency audit reported no known vulnerabilities in the locked versions.
- Replaced the development Tailwind CDN with generated local CSS and a locked build. Patched the build dependency tree; npm audit reported zero vulnerabilities.
- Restricted login/admin/registration redirects to the application host. Removed untrusted Referer redirects from listing actions.
- Enforced Django password validators and email validation at registration, password validators on password changes, and shared-cache authentication request limits. Added general API throttling. Production trusts forwarded client IPs only when explicitly configured behind the private proxy network.
- Enabled and migrated JWT refresh-token blacklisting; tested that rotated tokens cannot be reused.
- Added shared image content/size/pixel validation, JPEG re-encoding, EXIF removal, and upload/request limits. Applied validation across HTML uploads and REST image serializers. Production media uses a separate origin; private evidence remains inaccessible to the public file server.
- Restricted canonical book metadata edits to staff. Seller cover replacements update the actual-copy photos rather than the shared catalog cover. Added tests with two sellers using the same catalog book.
- Removed public Nominatim calls from autocomplete. Local neighborhood/database suggestions and manual pins remain available. External geocoding is disabled by default; optional explicit lookups require an identifying client, configurable endpoint, and shared aggregate rate limit.
- Validated original price, edition year, catalog input lengths, and malformed chat API payloads. Bounded chat text, initial message history, thread lists, seller listings, and pickup history, with navigation to older records.
- Removed automatic sample-address creation from profile visits. Updated password hints and pickup-only wording, including leftover footer checkout text and placeholder homepage copy.
- Added production environment template, a non-root Gunicorn image, private-network production Compose stack, Caddy HTTPS/static/media configuration, worker/scheduler services, database/cache health checks, an expiry management command, and deployment/backup instructions.

## Verification

- PostgreSQL application suite: 49 tests passed, including concurrent reservation acceptance and new security regressions.
- Django normal checks passed; no missing migrations.
- Deployment checks passed with a strong generated test secret and explicit sample hosts. Real production credentials/domains were not changed or invented.
- Public-page smoke requests and template compilation passed.
- Desktop/mobile headless browser previews of the compiled CSS: no JavaScript errors or horizontal overflow. External font/icon CDNs were blocked in that isolated preview; the layout itself used local CSS.
- Production Compose configuration validated.
- Container build/run could not be tested because the local Docker Desktop Linux engine is not running.

## Still required on the hosting server

Configure real DNS/application/media hosts, secrets, SMTP, proxy network, storage, and off-host backups. Build/run the Linux containers, verify TLS and media isolation, verify password-reset email delivery, demonstrate scheduled reservation expiry, test the complete buyer/seller flow on staging, perform a backup restore drill, and configure alerting. No public deployment was performed.

See [production-deployment.md](production-deployment.md) for setup and release verification.
