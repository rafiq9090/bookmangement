from urllib.parse import urlparse
from uuid import uuid4
from django.conf import settings
from django.core.cache import cache
from django.core.management.base import BaseCommand, CommandError
from django.db import connection


class Command(BaseCommand):
    help = 'Check production configuration, database, cache and migrations without deploying.'

    def handle(self, *args, **options):
        problems = []
        if settings.DEBUG:
            problems.append('DEBUG must be False.')
        hosts = settings.ALLOWED_HOSTS
        if not hosts or any(h in ['*', 'localhost', '127.0.0.1', 'testserver'] or h.endswith('.example.com') for h in hosts):
            problems.append('Set real explicit application hosts.')
        media = urlparse(settings.MEDIA_URL)
        if media.scheme != 'https' or not media.hostname or media.hostname in hosts:
            problems.append('MEDIA_URL must use a separate HTTPS media origin.')
        if not settings.CSRF_TRUSTED_ORIGINS or any(not o.startswith('https://') for o in settings.CSRF_TRUSTED_ORIGINS):
            problems.append('Configure HTTPS CSRF_TRUSTED_ORIGINS.')
        if settings.EMAIL_HOST in ['', 'localhost'] or not settings.DEFAULT_FROM_EMAIL or settings.DEFAULT_FROM_EMAIL.endswith('@localhost'):
            problems.append('Configure a real SMTP host and sender, then verify delivery.')
        push = [settings.WEB_PUSH_PUBLIC_KEY, settings.WEB_PUSH_PRIVATE_KEY, settings.WEB_PUSH_SUBJECT]
        if any(push) and not all(push):
            problems.append('Push requires all three WEB_PUSH settings.')
        if all(push) and 'localhost' in settings.WEB_PUSH_SUBJECT:
            problems.append('Set a real VAPID contact subject.')
        try:
            connection.ensure_connection()
            from django.db.migrations.executor import MigrationExecutor
            executor = MigrationExecutor(connection)
            if executor.migration_plan(executor.loader.graph.leaf_nodes()):
                problems.append('Apply pending database migrations.')
        except Exception:
            problems.append('Database connectivity check failed.')
        try:
            key = 'production-preflight:' + uuid4().hex
            if 'redis' not in settings.CACHES['default']['BACKEND'].lower():
                problems.append('Configure shared Redis cache for production rate limits.')
            cache.set(key, 'ok', 30)
            if cache.get(key) != 'ok':
                problems.append('Shared cache read/write failed.')
            cache.delete(key)
        except Exception:
            problems.append('Redis cache connectivity check failed.')
        if problems:
            raise CommandError('\n'.join(problems))
        self.stdout.write('Configuration, database and cache checks passed. Still verify TLS, workers, delivery, restore and monitoring on staging.')
