from django.core.management.base import BaseCommand
from apps.orders.services.pickup import expire_reservations


class Command(BaseCommand):
    help = 'Release expired pickup reservations. Safe to schedule every minute.'

    def handle(self, *args, **options):
        self.stdout.write(f'Expired {expire_reservations()} pickup reservations.')
