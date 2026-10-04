# Custom marketplace administration

Open `/admin-login/` and `/admin/dashboard/`. The console now covers Overview,
Listings, Users & Sellers, Pickups, Reports, Categories & Authors, and Activity
Log. Courier, escrow, commission and payout screens were removed.

Each list supports search and pagination (25 rows); transaction lists also
support status filters. Moderation requires a reason and confirmation. Reserved
or completed transactions cannot be changed through listing moderation.
Disputes use the existing transactional resolution service.

Run `python manage.py setup_admin_roles` after migrations to create Moderator,
Catalog Editor and Account Manager groups. Set a user's staff flag and assign
only the needed groups using Django technical administration. Superusers have
full access; staff with no group can inspect the console but cannot modify
records. Staff accounts cannot be suspended through this console.

AdminActivity records actor, target, reason and before/after values for console
changes. The activity page is read-only. Django technical administration remains
available for maintenance; its changes use Django's own LogEntry separately.

Overview displays pending push deliveries and overdue reservations; these are
database queue indicators, not proof that workers or external services are up.
Use the existing expiry/retry management commands for recovery.
