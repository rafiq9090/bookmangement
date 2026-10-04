from django.core.management.base import BaseCommand
from apps.accounts.models import PushDelivery
from apps.accounts.push_tasks import deliver_push


class Command(BaseCommand):
    help = "Queue up to 100 pending browser push alerts."

    def handle(self, *args, **options):
        count = 0
        for pk in PushDelivery.objects.filter(sent_at__isnull=True).values_list('pk', flat=True)[:100]:
            deliver_push.delay(pk)
            count += 1
        self.stdout.write(f"Queued {count} push alerts.")
