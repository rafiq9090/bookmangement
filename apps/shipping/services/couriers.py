from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from apps.orders.models import Order, OrderShipment
from apps.payments.services.ledger import release_escrow_to_seller
from apps.shipping.models import TrackingEvent


def dispatch_shipment(shipment: OrderShipment, courier_name: str, tracking_number: str) -> OrderShipment:
    """Updates shipment with courier assignment and marks in-transit."""
    if shipment.order.status != Order.Status.PAID:
        raise ValidationError("Cannot dispatch shipment until customer payment is confirmed.")

    shipment.courier_name = courier_name
    shipment.tracking_number = tracking_number
    shipment.status = OrderShipment.ShipmentStatus.IN_TRANSIT
    shipment.dispatched_at = timezone.now()
    shipment.save(update_fields=["courier_name", "tracking_number", "status", "dispatched_at"])

    TrackingEvent.objects.create(
        shipment=shipment,
        event_name="Dispatched by Seller",
        location="Origin Hub",
    )
    return shipment


def record_tracking_event(
    shipment: OrderShipment,
    event_name: str,
    location: str = "",
    is_delivered: bool = False,
    raw_payload: dict | None = None,
) -> TrackingEvent:
    """Registers courier milestone. If final delivery occurs, releases escrow."""
    with transaction.atomic():
        event = TrackingEvent.objects.create(
            shipment=shipment,
            event_name=event_name,
            location=location,
            raw_payload=raw_payload or {},
        )

        if is_delivered:
            shipment.status = OrderShipment.ShipmentStatus.DELIVERED
            shipment.delivered_at = timezone.now()
            shipment.save(update_fields=["status", "delivered_at"])

            # Release escrow earnings into seller available ledger
            release_escrow_to_seller(shipment)

            # Check if all sibling shipments are complete
            parent_order = shipment.order
            all_delivered = not parent_order.shipments.exclude(
                status=OrderShipment.ShipmentStatus.DELIVERED
            ).exists()
            if all_delivered:
                parent_order.status = Order.Status.COMPLETED
                parent_order.save(update_fields=["status", "updated_at"])

    return event
