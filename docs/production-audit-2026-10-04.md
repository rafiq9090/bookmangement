# Production audit — 2026-10-04

Remediation update: the code issues have now been addressed. See production-remediation-2026-10-04.md for changes and current verification. The findings below describe the state before those fixes.

Verdict at audit time: not ready for public production. Application tests pass, but deployment and operational verification remain incomplete.

## Verified

- Complete Django suite: 78 tests passed in 91.108 seconds. Redis timeouts triggered existing database-locking fallbacks; this does not verify Redis or workers.
- No missing model migrations (`makemigrations --check --dry-run`).
- Production `check --deploy` with temporary audit-only host and secret: no Django security warnings; one drf-spectacular schema warning for ConversationSerializer.get_messages. These temporary inputs are not production configuration.
- npm audit --omit=dev: zero reported vulnerabilities. CSS build development dependencies were excluded.
- Current Python dependency scan could not run: pip_audit is unavailable. Earlier dependency results do not certify the newly added push dependencies.
- Docker CLI is present, but Docker Desktop Linux engine is unavailable. No production image build or container smoke test was completed.
- .env.production is absent.

## Launch blockers

1. Configure a real production environment: app/media domains, independent secret, database credentials, SMTP sender, HTTPS origins. Build and start the supplied deployment stack in staging; verify HTTPS, cookies, static/media, private upload isolation, migrations, and role setup. Rotate local/demo admin credentials before launch.
2. Verify Redis, Celery worker and scheduler, reservation expiry, message notifications, and actual push delivery. .env.production.example currently omits WEB_PUSH_PUBLIC_KEY, WEB_PUSH_PRIVATE_KEY, and WEB_PUSH_SUBJECT. Broker failure leaves push outbox records pending; the retry command is manual, with no periodic outbox recovery configured.
3. Configure password-reset email delivery, off-host database/media/evidence backups, a successful restore drill, log retention, and alerts. Their configuration and operation were not established by this audit.
4. Correct misleading book-detail content: templates/books/book_detail.html uses a fixed Save 50% badge when original_mrp exists, a fabricated price fallback (3.36), and an unrelated default book description. Compare actual price/MRP or omit claims; use truthful unavailable states.
5. Harden public submissions: contact form's session-only one-minute limit can be bypassed with a new session; listing reports have no per-user rate limit or duplicate suppression. Add shared-cache rate limits and validate details length rather than silently truncating. Verify spam/flood behavior.
6. Run a current Python dependency vulnerability scan and clean production install/build. Complete a staging browser walkthrough of seller listing, buyer messaging/offers/pickups, report moderation, contact forms, staff permissions, mobile and tablet layouts. Load/concurrency testing under production infrastructure remains unverified.

## Further improvements

- Admin overview exposes cross-section aggregate counts to all staff. Narrow the dashboard if roles must be strictly isolated, including aggregate business information.
- Staff creation validates email before insertion, but concurrent duplicate submissions can raise an unhandled database IntegrityError. Return a friendly validation error.
- Fix the API schema warning with an explicit message-list serializer annotation.
- Review privacy copy against actual hosting/data practices before launch; no legal compliance certification was performed.

Reference checklist: https://docs.djangoproject.com/en/5.2/howto/deployment/checklist/

No application code, secrets, live inventory, or deployment was changed during this audit. This report records observed evidence and unverified checks; passing automated tests is not a production certification.
