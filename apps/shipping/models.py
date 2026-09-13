from django.db import models
from apps.orders.models import OrderShipment


class CourierProvider(models.Model):
    name = models.CharField(max_length=50, unique=True)
    code = models.CharField(max_length=20, unique=True)
    api_base_url = models.URLField(blank=True)
    api_key = models.CharField(max_length=255, blank=True)
    is_active = models.BooleanField(default=True)

    def __str__(self) -> str:
        return self.name


class TrackingEvent(models.Model):
    shipment = models.ForeignKey(OrderShipment, on_delete=models.CASCADE, related_name="tracking_events")
    event_name = models.CharField(max_length=100)
    location = models.CharField(max_length=100, blank=True)
    timestamp = models.DateTimeField(auto_now_add=True)
    raw_payload = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["-timestamp"]
        verbose_name = "Tracking Event"
        verbose_name_plural = "Tracking Events"

    def __str__(self) -> str:
        return f"{self.event_name} @ {self.timestamp.strftime('%Y-%m-%d %H:%M')}"
