from drf_spectacular.utils import extend_schema, inline_serializer
from rest_framework import permissions, serializers as drf_serializers, status
from rest_framework.exceptions import PermissionDenied
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.orders.models import OrderShipment
from apps.shipping.services.couriers import dispatch_shipment, record_tracking_event


class DispatchShipmentView(APIView):
    permission_classes = (permissions.IsAuthenticated,)

    @extend_schema(
        request=inline_serializer(
            name="DispatchShipmentRequest",
            fields={
                "courier_name": drf_serializers.CharField(default="Steadfast"),
                "tracking_number": drf_serializers.CharField(),
            },
        ),
        responses={
            200: inline_serializer(
                name="DispatchShipmentResponse",
                fields={
                    "status": drf_serializers.CharField(),
                    "tracking_number": drf_serializers.CharField(),
                },
            )
        },
    )
    def post(self, request: Request, shipment_id: int) -> Response:
        try:
            shipment = OrderShipment.objects.select_related("order").get(id=shipment_id)
        except OrderShipment.DoesNotExist:
            return Response({"error": "Shipment not found."}, status=status.HTTP_404_NOT_FOUND)

        if shipment.seller != request.user and not request.user.is_staff:
            raise PermissionDenied("You can only dispatch shipments for your own seller account.")

        courier = request.data.get("courier_name", "Steadfast").strip()
        tracking = request.data.get("tracking_number", "").strip()
        if not tracking:
            return Response({"error": "Tracking number is required."}, status=status.HTTP_400_BAD_REQUEST)

        updated = dispatch_shipment(shipment=shipment, courier_name=courier, tracking_number=tracking)
        return Response({"status": "Dispatched", "tracking_number": updated.tracking_number})


class CourierWebhookView(APIView):
    """Public webhook receiver for delivery updates from couriers like Steadfast/RedX."""
    permission_classes = (permissions.AllowAny,)

    @extend_schema(
        request=inline_serializer(
            name="CourierWebhookRequest",
            fields={
                "tracking_number": drf_serializers.CharField(),
                "status": drf_serializers.CharField(),
                "hub_name": drf_serializers.CharField(required=False),
            },
        ),
        responses={200: inline_serializer(name="CourierWebhookResponse", fields={"status": drf_serializers.CharField()})},
    )
    def post(self, request: Request) -> Response:
        tracking_number = request.data.get("tracking_number") or request.data.get("consignment_id")
        event_status = request.data.get("status", "").upper()

        if not tracking_number:
            return Response({"error": "Missing tracking number identifier."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            shipment = OrderShipment.objects.select_related("order", "escrow").get(
                tracking_number=tracking_number
            )
        except OrderShipment.DoesNotExist:
            return Response({"error": "Shipment with this tracking number not found."}, status=status.HTTP_404_NOT_FOUND)

        is_delivered = event_status in ("DELIVERED", "DELIVERY_SUCCESS", "COMPLETED")
        record_tracking_event(
            shipment=shipment,
            event_name=event_status or "Status Update",
            location=request.data.get("hub_name", ""),
            is_delivered=is_delivered,
            raw_payload=dict(request.data),
        )

        return Response({"status": "Tracking event recorded"}, status=status.HTTP_200_OK)
