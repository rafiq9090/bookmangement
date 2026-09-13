from rest_framework import serializers
from apps.shipping.models import CourierProvider, TrackingEvent


class CourierProviderSerializer(serializers.ModelSerializer):
    class Meta:
        model = CourierProvider
        fields = ("id", "name", "code", "is_active")


class TrackingEventSerializer(serializers.ModelSerializer):
    class Meta:
        model = TrackingEvent
        fields = ("id", "event_name", "location", "timestamp")
