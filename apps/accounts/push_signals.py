import logging
from django.db import transaction
from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import PushDelivery, PushSubscription


def enqueue(user_id, key, title, url):
    if not PushSubscription.objects.filter(user_id=user_id).exists():
        return
    delivery, _ = PushDelivery.objects.get_or_create(event_key=key, defaults={"user_id": user_id, "title": title, "url": url})
    def dispatch():
        from .push_tasks import deliver_push
        try:
            deliver_push.delay(delivery.pk)
        except Exception:
            logging.getLogger(__name__).warning("Push retained in outbox for retry")
    transaction.on_commit(dispatch)


@receiver(post_save, sender="messaging.InquiryMessage")
def message_push(sender, instance, created, raw=False, **kwargs):
    if not created or raw:
        return
    conversation = instance.conversation
    recipient = conversation.seller_id if instance.sender_id == conversation.buyer_id else conversation.buyer_id
    enqueue(recipient, f"message:{instance.pk}", "New book message", f"/inbox/{conversation.pk}/")


@receiver(post_save, sender="orders.MarketplaceNotification")
def marketplace_push(sender, instance, created, raw=False, **kwargs):
    if created and not raw:
        enqueue(instance.user_id, f"notification:{instance.pk}", "Marketplace update", "/pickups/")
