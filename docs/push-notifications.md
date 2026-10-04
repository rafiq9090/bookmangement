# Browser push notifications

Profile contains a per-device Enable/Disable control. Permission is requested
only after clicking Enable. HTTPS is required in production; localhost works
for development. iOS requires installation to the Home Screen.

Local development keys are stored in the ignored `.env` file. Restart the web
server after changing configuration. The development subject is
`https://localhost`; replace it with your real site URL or mailto contact for
production. Logging out removes the subscription associated with that session.

Set WEB_PUSH_PUBLIC_KEY, WEB_PUSH_PRIVATE_KEY and WEB_PUSH_SUBJECT (a real
mailto contact) in the environment. Never commit the private key. Keep keys
stable across deployments so existing browser subscriptions remain valid.
Install pywebpush from requirements/base.txt and run Django migrations.
Run the existing Celery worker to send pending alerts.

Messages and marketplace notifications create a PushDelivery outbox entry.
Alert text is generic for lock-screen privacy. Expired endpoints are removed.
Transient failures retry three times. Unsent rows can be retried with
`python manage.py retry_push` after worker outages.

Push endpoints are limited to known browser push services to prevent requests
to arbitrary servers. Extend WEB_PUSH_ALLOWED_HOSTS deliberately for other
browser services. The worker does not cache pages or private responses.
