from django.contrib import admin
from apps.shipping.models import CourierProvider, TrackingEvent


@admin.register(CourierProvider)
class CourierProviderAdmin(admin.ModelAdmin):
    list_display = ("name", "code", "is_active")


@admin.register(TrackingEvent)
class TrackingEventAdmin(admin.ModelAdmin):
    list_display = ("shipment", "event_name", "location", "timestamp")
    list_filter = ("event_name", "timestamp")
    search_fields = ("shipment__tracking_number", "event_name")
