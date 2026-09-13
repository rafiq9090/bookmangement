import logging
import redis
from django.conf import settings
from django.db import transaction
from apps.listings.models import BookListing

logger = logging.getLogger(__name__)

TTL_SECONDS = getattr(settings, "RESERVATION_TTL_SECONDS", 900)


def get_redis_connection() -> redis.Redis | None:
    try:
        client = redis.Redis.from_url(
            settings.REDIS_URL,
            decode_responses=True,
            socket_connect_timeout=0.2,
            socket_timeout=0.2,
        )
        client.ping()
        return client
    except Exception as exc:
        logger.warning(f"Redis is unavailable, falling back to database ACID locking: {exc}")
        return None


def acquire_listing_reservation(listing_id: int, buyer_id: int) -> bool:
    """
    Acquires an exclusive 15-minute checkout reservation on a single-copy used book.
    Ensures both Redis memory lock and PostgreSQL transactional status state.
    """
    lock_key = f"lock:listing:{listing_id}"
    r = get_redis_connection()
    
    if r:
        acquired = r.set(lock_key, str(buyer_id), nx=True, ex=TTL_SECONDS)
        if not acquired:
            return False

    try:
        with transaction.atomic():
            listing = BookListing.objects.select_for_update(nowait=True).get(id=listing_id)
            if listing.status != BookListing.Status.ACTIVE or listing.is_deleted:
                if r:
                    r.delete(lock_key)
                return False

            listing.status = BookListing.Status.RESERVED
            listing.save(update_fields=["status", "updated_at"])
            return True
    except Exception as exc:
        if r:
            r.delete(lock_key)
        logger.error(f"Error during listing #{listing_id} reservation: {exc}")
        return False


def release_listing_reservation(listing_id: int) -> None:
    """Restores listing back to ACTIVE state and clears Redis key."""
    lock_key = f"lock:listing:{listing_id}"
    r = get_redis_connection()
    if r:
        r.delete(lock_key)

    try:
        with transaction.atomic():
            listing = BookListing.objects.select_for_update().get(id=listing_id)
            if listing.status == BookListing.Status.RESERVED:
                listing.status = BookListing.Status.ACTIVE
                listing.save(update_fields=["status", "updated_at"])
    except BookListing.DoesNotExist:
        pass
