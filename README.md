# Local P2P Used & Rare Book Marketplace

A Django modular monolith for finding physical book copies nearby, agreeing a price,
reserving one copy, arranging private pickup, inspecting/paying in person, and
confirming handover. Existing courier orders, payments and ledger tables are retained
as history. Local pickup is enabled by default.

## Run locally

Use Python 3.12+ and the dependencies in `requirements/base.txt`:

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements/base.txt
# Configure .env using .env.example, then start PostgreSQL and Redis.
docker compose up -d
python manage.py migrate
python manage.py runserver
```

The PostgreSQL role must be able to enable `pg_trgm` (or a database administrator
must install it beforehand). It supports the existing fuzzy catalogue search.
Run Celery worker and Beat for automatic reservation expiry:

```powershell
celery -A config worker --loglevel=info
celery -A config beat --loglevel=info
```

Redis is not required for correctness of pickup reservations: PostgreSQL row locks
and a partial unique constraint protect copies. Beat still needs its configured
broker. Participant actions also detect expired reservations; automatic restocking
requires the scheduled worker.

## Main pages

- `/store/`: search with district/area filters.
- `/sell/`: any signed-in user can list an actual copy with photos and a public area.
- `/inbox/`: listing chat.
- `/pickups/`: purchases, sales and in-app notifications.
- `/pickups/<id>/`: offers, pickup proposals, handover, reports and seller reviews.
- `/password-reset/`: password recovery; configure SMTP for deployed use.
- `/admin/orders/marketplacereport/`: moderation and dispute resolution links.

## Maintenance and API

See [docs/pickup-architecture.md](docs/pickup-architecture.md) for lifecycle rules,
API examples, privacy boundaries and migration notes. Previous design documentation
is preserved in [docs/legacy-architecture.md](docs/legacy-architecture.md).

Tests:

```powershell
python manage.py test --settings=config.settings.test
python manage.py test --settings=config.settings.test_postgres
python manage.py makemigrations --check --dry-run
python manage.py check
```

SQLite tests cover behavior; PostgreSQL tests also exercise simultaneous acceptance
in separate connections. Tests create their own database and do not alter live records.

## Maps and notifications

Leaflet 1.9.4 displays OpenStreetMap standard raster tiles. District/area input and
manual pins need no geocoding API. Public coordinates are rounded to two decimals;
exact private pickup coordinates are stored only on participant agreements.
Keep attribution visible, respect caching and do not bulk download map tiles.
The public tile service has no published quota or availability guarantee:
https://operations.osmfoundation.org/policies/tiles/

Notifications are persisted in-app for messages and agreement changes. SMS/email
transaction alerts are not configured. Password reset uses console mail locally and
SMTP configuration in production.

## Deployment

Production requires explicit `SECRET_KEY` and `ALLOWED_HOSTS`. Use HTTPS, persistent
media storage, PostgreSQL, and a running scheduled worker. Do not disable pickup mode
until legacy payment/courier validation has been hardened. The legacy checkout is
not suitable for accepting real payments.

## This Windows workspace

The existing virtualenv points to a Python installation that is no longer present.
A small launcher uses the bundled runtime with the installed project packages:

```powershell
.\scripts\django.ps1 runserver
.\scripts\django.ps1 test --settings=config.settings.test_postgres --noinput
```

For a standalone environment, recreate the virtualenv with an installed Python and
use the standard commands above.

## Production deployment

Use the locked production dependencies and generated local CSS. See [production fixes](docs/production-fixes.md) and [deployment setup](docs/production-deployment.md). Do not use local/test settings on a public host.
