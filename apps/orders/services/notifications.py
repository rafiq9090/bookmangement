"""Durable in-app notification outbox; external delivery is opt-in configuration."""
import logging
from django.conf import settings
from django.db import transaction
from django.core.mail import send_mail
from django.utils import timezone
from django.utils.module_loading import import_string
from apps.orders.models import MarketplaceNotification

logger = logging.getLogger(__name__)


def queue_delivery(notification_id):
    if not (settings.TRANSACTION_EMAIL_ENABLED or settings.TRANSACTION_SMS_ENABLED):
        return
    from apps.orders.tasks import deliver_notification
    try:
        deliver_notification.delay(notification_id)
    except Exception:
        # Beat retries persisted unsent records when the broker recovers.
        logger.warning('Notification retained for delivery retry', exc_info=True)


def send_notification(user, text, conversation=None):
    notification = MarketplaceNotification.objects.create(user=user, text=text[:255], conversation=conversation)
    transaction.on_commit(lambda: queue_delivery(notification.pk))
    return notification


@transaction.atomic
def deliver(notification_id):
    notification = MarketplaceNotification.objects.select_for_update().select_related('user').get(pk=notification_id)
    user = notification.user
    if not user.is_active:
        return
    try:
        if settings.TRANSACTION_EMAIL_ENABLED and user.email_notifications and not notification.email_sent_at:
            send_mail('Book marketplace update', notification.text + '\n\nVisit your marketplace account for details.',
                      settings.DEFAULT_FROM_EMAIL, [user.email], fail_silently=False)
            notification.email_sent_at = timezone.now()
        if settings.TRANSACTION_SMS_ENABLED and user.sms_notifications and user.phone_number and not notification.sms_sent_at:
            if not settings.TRANSACTION_SMS_BACKEND:
                raise ValueError('Configure TRANSACTION_SMS_BACKEND')
            import_string(settings.TRANSACTION_SMS_BACKEND)(user.phone_number, notification.text)
            notification.sms_sent_at = timezone.now()
        notification.last_delivery_error = ''
    except Exception as exc:
        # Store only the exception type, never provider credentials or payloads.
        notification.last_delivery_error = type(exc).__name__
        logger.warning('Notification delivery failed: %s', type(exc).__name__)
    notification.delivery_attempts += 1
    notification.save(update_fields=['email_sent_at', 'sms_sent_at', 'delivery_attempts', 'last_delivery_error'])
