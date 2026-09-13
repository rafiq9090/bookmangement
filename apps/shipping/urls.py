from django.urls import path
from apps.shipping.views import CourierWebhookView, DispatchShipmentView

app_name = "shipping"

urlpatterns = [
    path("dispatch/<int:shipment_id>/", DispatchShipmentView.as_view(), name="dispatch"),
    path("webhook/", CourierWebhookView.as_view(), name="courier-webhook"),
]
