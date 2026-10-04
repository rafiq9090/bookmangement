# Book ReSeller

A local marketplace for buying and selling used and rare books. Buyers discover copies, chat with sellers, make offers, arrange pickup, inspect and pay in person, and confirm handover.

## Status

Application features and automated checks are implemented. Public production deployment is not yet verified. Docker image execution, live HTTPS, SMTP, browser push delivery, off-host backup restoration, monitoring and staging load tests still require the hosting environment. Visitor capacity has not been benchmarked.

See [latest remediation](docs/production-remediation-2026-10-04.md) and [deployment guide](docs/production-deployment.md). Earlier audits describe their dated snapshots; test counts are not a permanent readiness guarantee.

## Stack and features

- Django / Django REST Framework, PostgreSQL, Redis, Celery and Gunicorn.
- Search by title, author or ISBN; category and district/area filters.
- Consent-based session recommendations using reading interests and optional location.
- Seller listings and photos, messaging, offers, pickup agreements and handover confirmation.
- Listing reports, contact form messages and audited moderation.
- Custom admin dashboard with role-restricted sections and owner-managed staff accounts.
- Password reset by email; optional browser push notifications.
- Separate mobile, tablet and desktop styles, locally compiled Tailwind CSS and branded 404 page.
- Contact, Privacy and About pages; cookie preferences.

Legacy payment/courier tables are retained for history. Local pickup is the supported flow; do not enable legacy online payments for real transactions without a separate review.

## Local setup

Requirements: Python 3.12+, PostgreSQL 16 and Redis 7. Node/npm is needed only to build CSS. Docker Desktop can run the local database/cache services.

From the project directory, using PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements/base.txt
Copy-Item .env.example .env
# Edit .env for your local database and settings before continuing.
docker compose up -d postgres redis
python manage.py migrate
python manage.py setup_admin_roles
python manage.py createsuperuser
npm ci --ignore-scripts
npm run build:css
python manage.py runserver
```

Do not overwrite an existing `.env`. Local database defaults are development-only. The PostgreSQL role must be able to enable `pg_trgm`, or a database administrator must install it before migrations. Windows users with this workspace's relocated Python environment can use `./scripts/django.ps1 runserver`; recreating the virtual environment is preferable for a standalone installation.

Run background services in separate terminals. On Windows use Celery's solo pool for development; production uses the Linux containers:

```powershell
celery -A config worker --loglevel=info --pool=solo
celery -A config beat --loglevel=info
```

Run exactly one Beat scheduler. Redis is needed for shared rate limits and Celery. PostgreSQL locking protects pickup state; fallback locking does not prove the worker or Redis is operating. Beat sweeps expired reservations every minute and retries pending push delivery every five minutes.

## Main pages

| Page | URL |
| --- | --- |
| Home | `/` |
| Browse books | `/store/` |
| Login / password recovery | `/login/`, `/password-reset/` |
| Seller application / new listing | `/seller/apply/`, `/sell/` |
| Seller inventory | `/seller/listings/` |
| Messages / pickups | `/inbox/`, `/pickups/` |
| Account | `/profile/` |
| Contact / Privacy / About | `/contact/`, `/privacy/`, `/about/` |
| Admin login / dashboard | `/admin-login/`, `/admin/dashboard/` |
| Admin staff management | `/admin/dashboard/?tab=staff` |
| Technical Django admin | `/admin/` |
| 404 preview / health | `/404/`, `/health/` |
| API schema / docs | `/api/schema/`, `/api/docs/` |

Create your own owner account. No default admin credentials belong in this repository.

## Admin roles

Only the owner (superuser) can create staff accounts, assign multiple roles and enable/disable access. Access changes are audited; owner accounts cannot be disabled through staff management.

| Role | Access |
| --- | --- |
| Marketplace Moderator | Listings, listing reports, pickup disputes, activity log |
| Catalog Editor | Categories, authors, activity log |
| Account Manager | Buyer/seller accounts, activity log |
| Support Agent | Contact messages, activity log |

Server-side permission checks protect sections and actions. Use `setup_admin_roles` after migration to configure the preset groups. See [custom admin](docs/custom-admin.md).

## Email and password reset

Local development defaults to console email. Reset messages appear in the Django terminal until SMTP is configured. Add your provider's values to the ignored `.env` (or `.env.production` for deployment):

```dotenv
EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend
EMAIL_HOST=your-provider-smtp-host
EMAIL_PORT=587
EMAIL_USE_TLS=True
EMAIL_HOST_USER=your-smtp-username
EMAIL_HOST_PASSWORD=your-smtp-password
DEFAULT_FROM_EMAIL=Book ReSeller <your-verified-sender@example.com>
```

This example assumes a provider supporting STARTTLS on port 587. Restart Django after changes. Test Forgot Password using an active registered account and verify inbox delivery. Reset links expire after one hour and become invalid after a successful reset. Keep credentials private.

## Push, recommendations and maps

Enable push from Profile on each device. Configure `WEB_PUSH_PUBLIC_KEY`, `WEB_PUSH_PRIVATE_KEY` and `WEB_PUSH_SUBJECT` together, use HTTPS in deployment, and keep VAPID keys stable. In-app messages do not require push permission. See [push notifications](docs/push-notifications.md).

Optional personalization uses a consent-gated session profile. Essential-only cookie choice disables interest learning. Location is accepted through explicit controls; nearby ranking requires location data. See [recommendations](docs/recommendations.md).

Maps use Leaflet and OpenStreetMap tiles. Manual area input/pins do not need an external geocoding provider. Public listing coordinates are approximate; exact pickup details are participant-only. Keep attribution and follow the [tile policy](https://operations.osmfoundation.org/policies/tiles/). External geocoding is disabled by default.

## Verification

```powershell
python manage.py test --settings=config.settings.test --noinput
python manage.py test --settings=config.settings.test_postgres --noinput
python manage.py makemigrations --check --dry-run
python manage.py check
npm run build:css
```

SQLite tests are fast behavioral checks. PostgreSQL tests exercise database-specific behavior, including simultaneous acceptance. Test databases are separate; the PostgreSQL role needs permission to create them. Do not use test settings/password hashers on a public host.

## Production Docker deployment

The production stack contains web, PostgreSQL, Redis, Celery worker, one scheduler and Caddy. Persistent volumes store the database, cache, public media, private evidence, static assets and certificates. Only proxy ports 80/443 are published; media uses a separate HTTPS origin.

1. Copy `.env.production.example` to `.env.production` and configure independent secrets, real application/media domains, database credentials and SMTP. Point DNS to the server and open ports 80/443.
2. Build CSS before the image: `npm ci --ignore-scripts` and `npm run build:css`.
3. On the Linux Docker host, run:

```bash
docker compose -f docker-compose.production.yml build
docker compose -f docker-compose.production.yml up -d postgres redis
docker compose -f docker-compose.production.yml run --rm web python manage.py migrate
docker compose -f docker-compose.production.yml run --rm web python manage.py collectstatic --noinput
docker compose -f docker-compose.production.yml run --rm web python manage.py setup_admin_roles
docker compose -f docker-compose.production.yml run --rm web python manage.py createsuperuser
docker compose -f docker-compose.production.yml run --rm web python manage.py check --deploy
docker compose -f docker-compose.production.yml run --rm web python manage.py production_preflight
docker compose -f docker-compose.production.yml up -d
```

Install production Python packages from `requirements/production.lock.txt`; the Dockerfile does this. Preflight checks configuration, migrations and DB/cache connectivity, but does not certify HTTPS or external delivery. Follow the [complete deployment guide](docs/production-deployment.md) for proxy trust, image access, SMTP, job verification and staging tests.

## Backups and monitoring

On the Linux host, `sh deploy/backup.sh /absolute/protected-backup-directory` creates a PostgreSQL dump, upload archive and checksums. Schedule it, encrypt and transfer backups off-host, and test restoration into a separate database and upload volumes. Container volumes are persistence, not backups. Never rehearse restoration over the live database.

Monitor HTTPS `/health/`, web/worker/scheduler failures, 5xx errors, overdue reservations, pending push growth and backup freshness. Configure alerts with your hosting provider. Complete mobile/tablet/desktop buyer and seller workflows plus load testing on staging before opening public registration.

## Repository hygiene

Keep source, migrations, lockfiles, generated `static/css/tailwind.css`, environment examples and audit documentation in Git. Keep real environment files, credentials, uploads, private evidence, local dependencies, logs and backup archives out of Git. Ignore rules do not remove files already tracked; review `git status` before committing.

Further documentation: [pickup architecture](docs/pickup-architecture.md), [responsive design](docs/responsive-design.md), [legacy architecture](docs/legacy-architecture.md).
