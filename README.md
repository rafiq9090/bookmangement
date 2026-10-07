# Book ReSeller

Book ReSeller is a non-profit, peer-to-peer (P2P) marketplace for buying and selling used and rare books with nearby readers. Buyers discover a copy, message the seller, agree on a public pickup, inspect the book, and pay the seller directly at handover. The platform charges no commission or transaction fee.

## How the marketplace works

1. A seller lists a book with its price, condition, photos, and pickup area.
2. A buyer searches for books, contacts the seller, and sends a purchase request.
3. The seller accepts the request, and both participants agree on a pickup time and public meeting place.
4. The buyer checks the book and pays the seller directly at pickup.
5. Both participants confirm the handover; the buyer can review the seller or report a problem.

Book ReSeller connects readers and helps coordinate the exchange. It does not collect the purchase payment, hold funds in escrow, deduct a percentage, or process seller payouts in this P2P workflow.

Legacy cart, shipping, wallet, and payment code remains in the repository from an earlier design. These modules are not the current marketplace business model. Any commission settings or escrow logic in that legacy code must not be interpreted as a platform charge or advertised as a current feature.

## Current features

- **Book discovery:** canonical book catalog, authors, categories, ISBN lookup, condition filters, pagination, and search suggestions for titles, authors, and ISBNs. Buyer category navigation shows categories with available books.
- **Nearby books:** optional browser location, location search, distance labels, and nearby sorting. Location requires browser permission; manual area search remains available.
- **Recommendations:** content-based ranking from category, author, and language interests, proximity, and freshness. Guest and signed-in preferences are browser-session based and personalization follows cookie preferences. This is metadata ranking, not a trained Facebook-style recommendation system.
- **Seller listings:** condition grading, copy-specific prices, photos, edition details, editing, archiving, and sold status.
- **Messaging:** listing-specific conversations, photo attachments, unread indicators, and price negotiation. Message updates use polling.
- **Pickup agreements:** purchase requests, acceptance and reservation, meeting proposals, cancellation, handover confirmation, seller reviews, and problem reporting. Cancellation uses a custom confirmation dialog.
- **Accounts:** buyer/seller profiles, saved addresses, password reset, password visibility controls, live password guidance, and Bangladeshi mobile-number format validation. Phone validation does not verify ownership by OTP.
- **Notifications:** per-device browser push preferences, a service worker, delivery outbox, retries, and recovery tasks. Delivery requires VAPID configuration and a running worker.
- **Information and support:** About, Privacy, Contact form, cookie preferences, and a branded 404 page. Contact submissions appear in the custom admin dashboard.
- **Responsive interface:** mobile bottom navigation, mobile Information menu, tablet layouts, sticky desktop/tablet navigation, and reusable page components.
- **Administration:** permission-based management of listings, users, pickups, reports, catalog, contact submissions, and activity logs. The owner manages staff roles.
- **API:** Django REST Framework endpoints, JWT authentication, and OpenAPI documentation.

## Stack and project layout

Python / Django 5.2, Django REST Framework, PostgreSQL 16, Redis 7, Celery, Pillow, and server-rendered templates with JavaScript and Tailwind CSS. Production container files use Gunicorn and Caddy.

```text
apps/
  accounts/     Authentication, profiles, staff roles, contact, cookies, push
  books/        Catalog, authors, categories, reviews, recommendations, search
  listings/     Seller copies, condition details, photos, listing lifecycle
  messaging/    Buyer/seller conversations and attachments
  orders/       Pickup agreements and legacy cart/order functionality
  payments/     Legacy payment, escrow, ledger, and payout functionality
  shipping/     Legacy shipment and tracking functionality
config/         Settings, routes, health endpoint, Celery configuration
static/         CSS, JavaScript, images, and SVG assets
templates/      Marketplace, account, pickup, and admin pages
requirements/   Dependency manifests and production lock file
deploy/         Caddy configuration and backup helper
scripts/        Development helpers
docs/           Architecture, deployment, and verification notes
```

## Local setup

Use Python 3.12, Node.js/npm for CSS builds, and Docker Compose for PostgreSQL and Redis. Run commands from the repository root.

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -r requirements/local.txt
Copy-Item .env.example .env
```

On Linux/macOS, activate with `source .venv/bin/activate` and copy with `cp .env.example .env`.

Update `.env` database credentials and Redis URLs to match your environment. Example values are for local development only; never commit credentials or reuse them in production.

```powershell
docker compose up -d postgres redis
python manage.py migrate
python manage.py createsuperuser
python manage.py setup_admin_roles
npm ci --ignore-scripts
npm run build:css
python manage.py runserver
```

Open [the local homepage](http://127.0.0.1:8000/). The development Compose file starts PostgreSQL and Redis; Django runs separately. Rebuild CSS after changes that introduce Tailwind utility classes.

On Windows, `scripts/django.ps1` is an alternative management-command helper when the configured Python runtime is available:

```powershell
.\scripts\django.ps1 check
```

Run the worker and scheduler in separate terminals to enable background processing:

```powershell
# Windows development worker
celery -A config worker --loglevel=info --pool=solo

# Scheduler: run only one instance
celery -A config beat --loglevel=info
```

On Linux, use `celery -A config worker --loglevel=info` without `--pool=solo`. Keep the scheduler running for reservation expiry and scheduled push recovery.

## Pages and API routes

| Feature | Route |
| --- | --- |
| Home / marketplace | `/` / `/store/` |
| Book detail / authors | `/books/<slug>/` / `/authors/` |
| Register / sign in | `/register/` / `/login/` |
| Password reset | `/password-reset/` |
| Profile and notification preferences | `/profile/` |
| Sell a book / seller listings | `/sell/` / `/seller/listings/` |
| Messages | `/inbox/` |
| Pickups / pickup detail | `/pickups/` / `/pickups/<id>/` |
| About / Contact / Privacy | `/about/` / `/contact/` / `/privacy/` |
| Custom admin sign in / dashboard | `/admin-login/` / `/admin/dashboard/` |
| Django model administration | `/admin/` |
| Marketplace API namespaces | `/api/v1/accounts/`, `/api/v1/books/`, `/api/v1/listings/`, `/api/v1/pickups/`, `/api/v1/messaging/` |
| Search suggestions | `/api/books/suggest/?q=...` |
| OpenAPI schema / Swagger / ReDoc | `/api/schema/` / `/api/docs/` / `/api/redoc/` |
| Health / 404 preview | `/health/` / `/404/` |

The custom admin dashboard is separate from Django's model administration. Create your own owner account with `createsuperuser`; no shared admin credentials are documented here.

## Staff roles

Run `python manage.py setup_admin_roles` to initialize the permission groups. A superuser can create and manage staff through the dashboard.

| Role | Responsibilities |
| --- | --- |
| Marketplace Moderator | Listings, reports, and pickup moderation |
| Catalog Editor | Authors and categories |
| Account Manager | User management |
| Support Agent | Contact submissions |
| Superuser / owner | All sections and staff management |

Visibility and actions depend on Django permissions. Administrative changes are recorded in the activity log.

## Email and browser push

Local password reset emails print to the server console by default. To send real emails, configure the SMTP provider in `.env` and restart Django:

```dotenv
EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend
EMAIL_HOST=smtp.your-provider.example
EMAIL_PORT=587
EMAIL_USE_TLS=True
EMAIL_HOST_USER=your-smtp-user
EMAIL_HOST_PASSWORD=your-smtp-password
DEFAULT_FROM_EMAIL=Book ReSeller <no-reply@your-domain.example>
```

Use your provider's actual credentials and verified sender domain. Test a reset email through to a successful password change; a successful form submission alone does not verify delivery.

Browser push requires `WEB_PUSH_PUBLIC_KEY`, `WEB_PUSH_PRIVATE_KEY`, and `WEB_PUSH_SUBJECT`, plus a running Celery worker. Production requires HTTPS and browser permission. Enable notifications from the profile's notification section. Keep the private key secret and preserve keys across deployments. See [push setup](docs/push-notifications.md).

## Checks and tests

```powershell
python manage.py check
python manage.py makemigrations --check --dry-run
python manage.py test --noinput
npm run build:css
```

The test suite includes authentication, password reset, recommendations, search suggestions, pickup workflows, contact submissions, push behavior, and admin permissions. Default database tests require a PostgreSQL user that can create the test database. Use a dedicated development/test database configuration.

`test_endpoints.py` is an additional endpoint smoke-test script; inspect its configuration before running it against a server. Test settings use development-only shortcuts and must never be used for deployment.

## Production deployment

Use [the deployment guide](docs/production-deployment.md) for the full sequence. The production Compose stack includes `web`, `worker`, `scheduler`, `proxy`, `postgres`, and `redis` with persistent volumes. Only Caddy publishes ports 80 and 443.

1. Copy `.env.production.example` to `.env.production` and configure real app/media domains, secrets, database credentials, SMTP, and push keys. Serve public uploads from a separate media origin.
2. Point DNS to the deployment host, install Docker Compose, and build CSS.
3. Build containers and start the database/cache:

```bash
docker compose -f docker-compose.production.yml build
docker compose -f docker-compose.production.yml up -d postgres redis
docker compose -f docker-compose.production.yml run --rm web python manage.py migrate
docker compose -f docker-compose.production.yml run --rm web python manage.py collectstatic --noinput
docker compose -f docker-compose.production.yml run --rm web python manage.py setup_admin_roles
docker compose -f docker-compose.production.yml run --rm web python manage.py createsuperuser
docker compose -f docker-compose.production.yml run --rm web python manage.py check --deploy
docker compose -f docker-compose.production.yml up -d
docker compose -f docker-compose.production.yml exec web python manage.py production_preflight
```

Caddy handles HTTPS for the configured domains. Keep private evidence outside public media serving. Use `requirements/production.lock.txt` for reproducible Python dependency installation; production images handle their dependencies through the Dockerfile.

Deployment files and checks do not certify a running production environment. Before launch, verify HTTPS, real email/push delivery, Redis, worker/scheduler operation, permissions, upload privacy, backups, and complete buyer/seller staging flows. Measure capacity with load tests; no visitor-count guarantee is established.

## Backups and monitoring

On the Linux Docker host:

```bash
sh deploy/backup.sh /absolute/protected-backup-directory
```

The helper writes a PostgreSQL dump, public/private upload archive, and checksums. It does not encrypt, upload, or schedule backups. Configure encrypted off-server storage, retention, and a scheduler; pause upload mutations for a consistent snapshot. Test restoration into an isolated staging database and upload volumes.

Monitor HTTPS health checks, 5xx responses, container restarts, worker/scheduler failures, overdue reservations, email failures, and pending push growth. Persistent Docker volumes are not a backup.

## Further documentation

- [Pickup architecture](docs/pickup-architecture.md)
- [Recommendations](docs/recommendations.md)
- [Custom administration](docs/custom-admin.md)
- [Browser push](docs/push-notifications.md)
- [Responsive design](docs/responsive-design.md)
- [Production deployment and restoration](docs/production-deployment.md)
- [Production audit](docs/production-audit-2026-10-04.md)
- [Production remediation notes](docs/production-remediation-2026-10-04.md)
- [Legacy architecture](docs/legacy-architecture.md)

Audit notes describe the checks performed at their recorded date, not the live status of a deployment.
