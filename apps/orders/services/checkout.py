from collections import defaultdict
from decimal import Decimal
from typing import Any
from django.db import transaction
from rest_framework.exceptions import ValidationError

from apps.accounts.models import CustomUser
from apps.listings.models import BookListing
from apps.orders.models import Cart, CartItem, Order, OrderItem, OrderShipment
from apps.orders.services.reservation import acquire_listing_reservation
from apps.payments.models import EscrowHold

DEFAULT_SHIPPING_FEE_PER_SELLER = Decimal("60.00")
PLATFORM_COMMISSION_RATE = Decimal("0.15")


def process_cart_checkout(buyer: CustomUser, shipping_address_data: dict[str, Any]) -> Order:
    """
    Executes multi-vendor checkout by grouping cart items per seller, acquiring TTL locks,
    splitting shipments, and initializing escrow balances.
    """
    try:
        cart = Cart.objects.prefetch_related("items__listing", "items__listing__seller").get(user=buyer)
    except Cart.DoesNotExist:
        raise ValidationError("Your shopping cart is empty.")

    cart_items = list(cart.items.all())
    if not cart_items:
        raise ValidationError("Your shopping cart contains no items.")

    # Group items by seller for shipment isolation
    seller_items_map: dict[CustomUser, list[BookListing]] = defaultdict(list)
    for item in cart_items:
        listing = item.listing
        if listing.seller_id == buyer.id:
            raise ValidationError(f"You cannot purchase your own book listing ({listing.book.title}).")
        seller_items_map[listing.seller].append(listing)

    # Acquire reservation lock for each listing
    reserved_listing_ids: list[int] = []
    for item in cart_items:
        success = acquire_listing_reservation(item.listing_id, buyer.id)
        if not success:
            raise ValidationError(
                f"The book '{item.listing.book.title}' is currently unavailable or being checked out by someone else."
            )
        reserved_listing_ids.append(item.listing_id)

    with transaction.atomic():
        # Calculate totals
        items_total = sum(item.listing.price for item in cart_items)
        shipping_total = Decimal(len(seller_items_map)) * DEFAULT_SHIPPING_FEE_PER_SELLER
        grand_total = items_total + shipping_total

        # 1. Create overarching Order
        order = Order.objects.create(
            buyer=buyer,
            shipping_address_snapshot=shipping_address_data,
            total_amount=grand_total,
            shipping_total=shipping_total,
            status=Order.Status.PENDING,
        )

        # 2. Split order into seller-specific shipments
        for seller, listings in seller_items_map.items():
            shipment_subtotal = sum(l.price for l in listings)
            shipment = OrderShipment.objects.create(
                order=order,
                seller=seller,
                shipping_fee=DEFAULT_SHIPPING_FEE_PER_SELLER,
                subtotal=shipment_subtotal,
                status=OrderShipment.ShipmentStatus.WAITING_SELLER,
            )

            for listing in listings:
                OrderItem.objects.create(
                    shipment=shipment,
                    listing=listing,
                    price_at_purchase=listing.price,
                )

            # 3. Create Escrow Hold record per shipment
            commission = (shipment_subtotal * PLATFORM_COMMISSION_RATE).quantize(Decimal("0.01"))
            seller_net = shipment_subtotal - commission
            EscrowHold.objects.create(
                order=order,
                shipment=shipment,
                gross_amount=shipment_subtotal,
                platform_fee=commission,
                seller_net_amount=seller_net,
                status=EscrowHold.EscrowStatus.HELD,
            )

        # 4. Clear buyer's cart
        cart.items.all().delete()

    return order
