import base64
import json
from unittest.mock import patch
from django.test import TestCase, override_settings
from apps.accounts.models import CustomUser, PushSubscription, PushDelivery
from apps.orders.models import MarketplaceNotification
from apps.accounts.push_tasks import deliver_push


@override_settings(WEB_PUSH_PUBLIC_KEY="public", WEB_PUSH_PRIVATE_KEY="private", WEB_PUSH_SUBJECT="https://localhost")
class PushTests(TestCase):
    def setUp(self):
        self.user = CustomUser.objects.create_user(email="push@example.com", password="StrongPass123!")
        self.client.force_login(self.user)
        encode = lambda value: base64.urlsafe_b64encode(value).decode().rstrip("=")
        self.data = {"endpoint": "https://fcm.googleapis.com/fcm/send/test", "keys": {"p256dh": encode(b"x" * 65), "auth": encode(b"a" * 16)}}

    def subscribe(self, data=None):
        return self.client.post("/notifications/push/subscription/", data=json.dumps(data or self.data), content_type="application/json")

    def test_subscribe_and_unsubscribe(self):
        self.assertEqual(self.subscribe().status_code, 200)
        self.assertEqual(PushSubscription.objects.get().user, self.user)
        self.assertEqual(self.subscribe({"endpoint": self.data["endpoint"], "unsubscribe": True}).status_code, 200)
        self.assertFalse(PushSubscription.objects.exists())

    def test_rejects_private_endpoint_and_invalid_keys(self):
        data = dict(self.data, endpoint="https://127.0.0.1/private")
        self.assertEqual(self.subscribe(data).status_code, 400)
        self.assertEqual(self.subscribe(dict(self.data, keys={"auth": "bad", "p256dh": "bad"})).status_code, 400)

    def test_requires_authentication(self):
        self.client.logout()
        self.assertEqual(self.subscribe().status_code, 302)

    def test_logout_removes_device_subscription(self):
        self.subscribe()
        self.client.get("/logout/")
        self.assertFalse(PushSubscription.objects.exists())

    def test_marketplace_event_queues_and_sends_generic_alert(self):
        self.subscribe()
        MarketplaceNotification.objects.create(user=self.user, text="Private pickup details")
        delivery = PushDelivery.objects.get()
        with patch("pywebpush.webpush") as send:
            deliver_push.run(delivery.pk)
            payload = json.loads(send.call_args.kwargs["data"])
            self.assertNotIn("Private", payload["body"])
            self.assertEqual(payload["url"], "/pickups/")
        delivery.refresh_from_db()
        self.assertIsNotNone(delivery.sent_at)
