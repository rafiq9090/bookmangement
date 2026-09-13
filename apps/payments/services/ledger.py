from typing import Any
from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from apps.listings.models import BookListing
from apps.orders.models import Order, OrderShipment
from apps.orders.services.reservation import get_redis_connection
from apps.payments.models import EscrowHold, Payment, SellerLedger


def confirm_payment_and_finalize_order(
    order: Order,
    transaction_id: str,
    gateway_name: str = Payment.Gateway.SSLCOMMERZ,
    raw_response: dict[str, Any] | None = None,
) -> Payment:
    """
    Idempotently records payment, marks order as PAID, transitions reserved listings
    to SOLD, and purges Redis temporary checkout locks.
    """
    with transaction.atomic():
        payment, created = Payment.objects.get_or_create(
            order=order,
            defaults={
                "gateway": gateway_name,
                "transaction_id": transaction_id,
                "amount": order.total_amount,
                "status": Payment.Status.SUCCESS,
                "raw_response": raw_response or {},
            },
        )

        if not created and payment.status == Payment.Status.SUCCESS:
            return payment

        # Transition order
        order.status = Order.Status.PAID
        order.save(update_fields=["status", "updated_at"])

        # Finalize all listings as permanently SOLD
        r = get_redis_connection()
        for shipment in order.shipments.prefetch_related("items__listing"):
            for item in shipment.items.all():
                listing = item.listing
                listing.status = BookListing.Status.SOLD
                listing.save(update_fields=["status", "updated_at"])
                
                if r:
                    try:
                        r.delete(f"lock:listing:{listing.id}")
                    except Exception:
                        pass

    return payment


def release_escrow_to_seller(shipment: OrderShipment) -> EscrowHold:
    """
    Invoked when delivery is verified or the dispute window passes.
    Releases held escrow funds into the seller's available ledger balance.
    """
    if shipment.status != OrderShipment.ShipmentStatus.DELIVERED:
        raise ValidationError("Cannot release escrow on a shipment that has not been confirmed delivered.")

    try:
        escrow = shipment.escrow
    except EscrowHold.DoesNotExist:
        raise ValidationError("No escrow record found for this shipment.")

    if escrow.status == EscrowHold.EscrowStatus.RELEASED:
        return escrow

    with transaction.atomic():
        escrow.status = EscrowHold.EscrowStatus.RELEASED
        escrow.released_at = timezone.now()
        escrow.save(update_fields=["status", "released_at"])

        # Record double-entry style accounting ledger credits
        SellerLedger.objects.create(
            seller=shipment.seller,
            entry_type=SellerLedger.EntryType.SALE_CREDIT,
            amount=escrow.seller_net_amount,
            reference_id=f"SHIPMENT-{shipment.id}-NET",
        )

    return escrow
