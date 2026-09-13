from datetime import timedelta
from celery import shared_task
from django.utils import timezone
from apps.listings.models import BookListing


@shared_task
def sweep_expired_reservations() -> str:
    """
    Periodically triggered by Celery Beat every 60 seconds.
    Identifies reservations older than 15 minutes that never culminated
    in completed payment, returning them to ACTIVE state.
    """
    threshold = timezone.now() - timedelta(minutes=15)
    expired_listings = BookListing.objects.filter(
        status=BookListing.Status.RESERVED,
        updated_at__lte=threshold,
        is_deleted=False,
    )

    count = expired_listings.update(status=BookListing.Status.ACTIVE)
    return f"Restocked {count} abandoned book reservations."
