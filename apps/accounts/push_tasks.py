import json
import logging
from celery import shared_task
from django.conf import settings
from django.utils import timezone
from .models import PushDelivery, PushSubscription


@shared_task
def recover_pending_push():
    if not settings.WEB_PUSH_PRIVATE_KEY:
        return 0
    queued = 0
    for pk in PushDelivery.objects.filter(sent_at__isnull=True).order_by('pk').values_list('pk', flat=True)[:100]:
        try:
            deliver_push.delay(pk)
            queued += 1
        except Exception:
            logging.getLogger(__name__).exception('Push recovery could not queue delivery %s', pk)
            break
    return queued


@shared_task(autoretry_for=(Exception,), retry_backoff=True, max_retries=3)
def deliver_push(delivery_id):
    from pywebpush import webpush, WebPushException
    delivery = PushDelivery.objects.get(pk=delivery_id)
    if delivery.sent_at or not settings.WEB_PUSH_PRIVATE_KEY:
        return
    for subscription in PushSubscription.objects.filter(user_id=delivery.user_id):
        try:
            webpush(subscription_info={"endpoint": subscription.endpoint, "keys": subscription.keys},
                    data=json.dumps({"title": delivery.title, "body": "Open Book ReSeller to view the update.", "url": delivery.url, "tag": delivery.event_key}),
                    vapid_private_key=settings.WEB_PUSH_PRIVATE_KEY,
                    vapid_claims={"sub": settings.WEB_PUSH_SUBJECT}, timeout=10, ttl=300)
        except WebPushException as error:
            if error.response is not None and error.response.status_code in (404, 410):
                subscription.delete()
            else:
                raise
    delivery.sent_at = timezone.now()
    delivery.save(update_fields=["sent_at"])
