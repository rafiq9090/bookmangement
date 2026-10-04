# Production remediation — 2026-10-04

Implemented:
- Removed fabricated book-detail price, fixed discount percentage and unrelated default description.
- Shared-cache per-IP and authenticated-user quotas for contact/report submission; rotating sessions no longer resets contact limits. Cache failure fails closed. Reports validate length and serialize duplicate checks using a per-user database lock.
- Staff creation database conflicts return form errors. Admin overview metrics respect section access and infrastructure status is owner-only.
- Celery beat queues pending push recovery every five minutes. Production environment example includes all VAPID settings. Push remains an at-least-once delivery system; browser notification tags deduplicate repeated display.
- Explicit API message-list schema annotation; production deploy checks now report no warnings.
- production_preflight command validates real hosts/media origins, SMTP configuration, VAPID completeness, migrations and DB/shared-cache connectivity. It does not prove external delivery or HTTPS.
- deploy/backup.sh creates restrictive-permission PostgreSQL and upload backups/checksums on a Linux Docker host. Encryption/off-host transfer, scheduling and restore rehearsal still require the hosting environment.

Verification:
- Full Django suite: 83 tests passed, including the initial five remediation tests.
- Final targeted remediation suite: 7 tests passed after adding cache-outage and role-overview checks and serialized report deduplication.
- Production check --deploy: zero issues with temporary audit host/secret, not actual live configuration.
- No missing migrations. CSS rebuilt. Clean dependency resolution dry-run passed on Windows Python 3.12; Linux Docker build remains unverified.
- pip-audit production lock: no known vulnerabilities. Result: dependency-audit-current.json. This is an advisory scan, not a security guarantee.

Remaining external work:
- Production domains/provider and SMTP provider details are needed; do not reuse local credentials.
- Docker engine is unavailable, so image build, live TLS/proxy/static/media testing and Linux backup execution remain unverified.
- Real Redis/worker/scheduler, SMTP password-reset delivery, browser push delivery, monitoring/alerts, encrypted off-host backups and restore drill remain to be verified on staging.
- Complete staging end-to-end browser and load/concurrency tests. Existing tests used database locking when Redis timed out.

Do not treat this remediation as public-production certification. See production-deployment.md for launch steps.
