# Production deployment

These files prepare deployment; they do not deploy the site or certify a hosting environment.

1. Copy `.env.production.example` to `.env.production`. Set the real application/media hosts, matching MEDIA_URL and CSRF origins, a strong unique secret, database password, and SMTP credentials. Point both DNS names to the host. The media origin must be separate from the application origin. Keep geocoding disabled unless you deliberately configure a compliant provider and identifying contact.
2. Run `npm ci --ignore-scripts` and `npm run build:css` after template/JS changes. The generated CSS is committed and runtime Node is unnecessary.
3. Build: `docker compose -f docker-compose.production.yml build`.
4. Start infrastructure: `docker compose -f docker-compose.production.yml up -d postgres redis`.
5. Run `docker compose -f docker-compose.production.yml run --rm web python manage.py migrate`.
6. Run `docker compose -f docker-compose.production.yml run --rm web python manage.py collectstatic --noinput`.
7. Run `docker compose -f docker-compose.production.yml run --rm web python manage.py check --deploy` and `createsuperuser`.
8. Start: `docker compose -f docker-compose.production.yml up -d`. Caddy provisions HTTPS. The application/worker/database/Redis have no published ports; only Caddy is exposed. The private evidence volume is never mounted into the public file server.

The worker and one scheduler process release expired reservations every minute. Do not run duplicate beat instances. An alternative scheduler may invoke `python manage.py expire_pickups` every minute. Monitor scheduler failures; health checks alone do not prove expiry jobs are running.

Verify before enabling public registration:

- `https://YOUR_APP_HOST/health/` returns 200, HTTP redirects to HTTPS, and session cookies are secure.
- Static CSS and public images load with DEBUG=False; private evidence cannot be fetched from static/media servers.
- SMTP delivers password reset messages using the application domain, not localhost. Configure SPF/DKIM with the email provider.
- Two test users can list, message, reserve, cancel, agree pickup, confirm handover, and report a dispute on desktop and mobile. Manual status changes must not bypass completed/disputed handovers.
- Monitor web/worker/proxy logs, 5xx errors, failed health checks, SMTP failures, and scheduler operation. Application logs go to stdout; configure host retention and alerting.
- Verify the reverse proxy preserves the real client IP used by authentication throttling. Only trust forwarded client headers from the internal proxy. Do not expose Gunicorn directly.

## Backups and restore

Schedule encrypted off-host backups of PostgreSQL, public media, and private evidence. Use `pg_dump -Fc` from the database container and copy its output to protected backup storage. Do not place backups under public media/static paths. Retain daily and weekly versions according to your recovery needs; restrict credentials and evidence access.

Perform a restore drill into a separate staging database and separate upload volumes using `pg_restore`, then verify listings, image references, user login, and private evidence. Record the achieved recovery time and data-loss window. Container volumes are persistence, not backups.

## Dependencies

`requirements/production.lock.txt` records the tested resolved Python packages, while package-lock.json locks CSS build dependencies. Install with `pip install -r requirements/production.lock.txt` when available. Review security updates and rerun tests before refreshing locks. Never use the fast test password hasher or test settings in production.

## Updated launch checks

After migration, run `setup_admin_roles` and `production_preflight` inside the web container. Create an independent production owner account; do not reuse local admin credentials. Configure all three WEB_PUSH settings to enable browser notifications. Beat retries pending push alerts every five minutes.

On the Linux Docker host, run `sh deploy/backup.sh /absolute/protected-backup-directory`. This creates a database dump, public/private upload archive and checksums with restrictive permissions. It does not encrypt or upload backups: configure encrypted off-host storage and schedule the script with your host scheduler. For a consistent snapshot, pause upload mutations during backup. Restore the database into a separate staging database with `pg_restore` and uploads into separate volumes, then verify image references and private evidence access. Never restore over the live environment as a test.

Configure your hosting monitor to alert on HTTPS /health/ failures, web/worker/beat restarts, 5xx errors, overdue reservations and pending push growth. SMTP delivery, push delivery, backups and alerts require real external services and a recorded staging walkthrough before launch.
