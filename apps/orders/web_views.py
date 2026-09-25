from collections import defaultdict
from decimal import Decimal
import uuid
from django.contrib import messages
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render

from apps.accounts.models import Address
from apps.listings.models import BookListing
from apps.orders.models import Cart, CartItem, Order, OrderItem, OrderShipment
from apps.orders.services.cart import get_cart_items_for_request
from apps.payments.models import EscrowHold, Payment
from apps.shipping.models import TrackingEvent


def cart_view(request):
    """
    Renders the Shopping Cart page with line items, condition badges,
    pricing, quantity summary, and estimated shipping.
    Requires user to be signed in. Unauthenticated users are redirected to login.
    """
    if not request.user.is_authenticated:
        messages.info(request, "Please log in to view and manage your shopping cart.")
        return redirect("/login/?next=/cart/")

    items, subtotal, cart_count = get_cart_items_for_request(request)
    shipping_fee = Decimal("2.00") if subtotal > 0 and subtotal < Decimal("30.00") else Decimal("0.00")
    total = subtotal + shipping_fee

    return render(
        request,
        "orders/cart.html",
        {
            "items": items,
            "subtotal": subtotal,
            "shipping_fee": shipping_fee,
            "total": total,
            "cart_count": cart_count,
        },
    )


def add_to_cart_view(request, listing_id):
    """
    Adds a book listing to the user's cart.
    Requires:
    1. Buyer must be signed in.
    2. Buyer cannot purchase their own listing.
    3. Buyer must have contacted seller and seller confirmed the order.
    """
    listing = get_object_or_404(BookListing, id=listing_id, status=BookListing.Status.ACTIVE, is_deleted=False)

    if not request.user.is_authenticated:
        messages.info(request, "Please log in and contact the seller to confirm the order before purchasing.")
        return redirect(f"/login/?next=/listings/{listing.id}/inquire/")

    if listing.seller_id == request.user.id:
        messages.warning(request, "You cannot purchase your own book listing.")
        return redirect("book_detail", slug=listing.book.slug)

    from apps.messaging.models import Conversation
    conv = Conversation.objects.filter(listing=listing, buyer=request.user).first()
    if not conv or conv.order_status != Conversation.OrderStatus.CONFIRMED:
        messages.warning(
            request,
            "Seller confirmation required: Please message the seller to confirm book availability before purchasing."
        )
        return redirect("start_inquiry", listing_id=listing.id)

    cart, _ = Cart.objects.get_or_create(user=request.user)
    existing_item = CartItem.objects.filter(listing=listing).first()
    if existing_item:
        if existing_item.cart_id != cart.id:
            existing_item.cart = cart
            existing_item.save(update_fields=["cart"])
    else:
        CartItem.objects.create(cart=cart, listing=listing)

    if request.GET.get("redirect") == "checkout":
        return redirect("checkout")
    return redirect("cart")


def remove_from_cart_view(request, item_id):
    """
    Removes a book listing from the user's database cart.
    Requires user to be signed in.
    """
    if not request.user.is_authenticated:
        return redirect("/login/?next=/cart/")

    CartItem.objects.filter(cart__user=request.user, id=item_id).delete()
    return redirect("cart")


def checkout_view(request):
    """
    Renders the Checkout page and processes order placement.
    Requires user account: guests cannot buy books without registering/signing in.
    """
    if not request.user.is_authenticated:
        messages.warning(request, "Please create an account or sign in to complete your book purchase.")
        return redirect("/login/?mode=register&next=/checkout/")

    items, subtotal, cart_count = get_cart_items_for_request(request)
    if not items:
        return redirect("cart")

    # Enforce Seller Confirmation Rule: All items in cart must be confirmed by their seller
    from apps.messaging.models import Conversation
    unconfirmed_titles = []
    for it in items:
        listing = it["listing"]
        confirmed = Conversation.objects.filter(
            listing=listing,
            buyer=request.user,
            order_status=Conversation.OrderStatus.CONFIRMED,
        ).exists()
        if not confirmed:
            unconfirmed_titles.append(f"'{listing.book.title}'")

    if unconfirmed_titles:
        messages.warning(
            request,
            f"Seller confirmation required for: {', '.join(unconfirmed_titles)}. Please contact the seller and wait for approval before checkout."
        )
        return redirect("inbox")

    shipping_fee = Decimal("2.00") if subtotal > 0 and subtotal < Decimal("30.00") else Decimal("0.00")
    total = subtotal + shipping_fee

    # Load buyer's default shipping address if saved
    default_address = Address.objects.filter(user=request.user, is_default=True).first() or Address.objects.filter(user=request.user).first()

    if request.method == "POST":
        full_name = request.POST.get("full_name", f"{request.user.first_name} {request.user.last_name}".strip() or "Valued Customer").strip()
        phone_number = request.POST.get("phone_number", request.user.phone_number or "").strip()
        street_address = request.POST.get("street_address", "").strip()
        city = request.POST.get("city", "Dhaka").strip()
        district = request.POST.get("district", "Dhaka").strip()
        postal_code = request.POST.get("postal_code", "").strip()
        payment_method = request.POST.get("payment_method", "bkash")

        address_snapshot = {
            "full_name": full_name,
            "phone_number": phone_number,
            "street_address": street_address,
            "city": city,
            "district": district,
            "postal_code": postal_code,
            "payment_method": payment_method,
        }

        buyer = request.user

        with transaction.atomic():
            is_paid = payment_method in ["bkash", "nagad", "card"]
            order = Order.objects.create(
                buyer=buyer,
                shipping_address_snapshot=address_snapshot,
                total_amount=total,
                shipping_total=shipping_fee,
                status=Order.Status.PAID if is_paid else Order.Status.PENDING,
            )

            # Record Payment
            gateway_map = {
                "bkash": Payment.Gateway.BKASH,
                "card": Payment.Gateway.STRIPE,
                "nagad": Payment.Gateway.SSLCOMMERZ,
            }
            payment_gateway = gateway_map.get(payment_method, Payment.Gateway.SSLCOMMERZ)
            Payment.objects.create(
                order=order,
                gateway=payment_gateway,
                transaction_id=f"TXN-{uuid.uuid4().hex[:10].upper()}",
                amount=total,
                status=Payment.Status.SUCCESS if is_paid else Payment.Status.INITIATED,
            )

            # Group items by seller
            seller_items_map = defaultdict(list)
            for it in items:
                seller_items_map[it["listing"].seller].append(it["listing"])

            for seller, listings in seller_items_map.items():
                shipment_subtotal = sum(l.price for l in listings)
                tracking_num = f"EB-{uuid.uuid4().hex[:8].upper()}"
                shipment = OrderShipment.objects.create(
                    order=order,
                    seller=seller,
                    shipping_fee=shipping_fee,
                    subtotal=shipment_subtotal,
                    courier_name="Steadfast Courier",
                    tracking_number=tracking_num,
                    status=OrderShipment.ShipmentStatus.WAITING_SELLER,
                )
                for l in listings:
                    OrderItem.objects.create(
                        shipment=shipment,
                        listing=l,
                        price_at_purchase=l.price,
                    )
                    # Mark physical listing as SOLD so it disappears from available store inventory
                    l.status = BookListing.Status.SOLD
                    l.save(update_fields=["status"])
                    Conversation.objects.filter(listing=l, buyer=request.user).update(
                        order_status=Conversation.OrderStatus.COMPLETED
                    )

                # Create Escrow Hold for consignment custody
                platform_commission = (shipment_subtotal * Decimal("0.10")).quantize(Decimal("0.01"))
                seller_net = shipment_subtotal - platform_commission
                EscrowHold.objects.create(
                    order=order,
                    shipment=shipment,
                    gross_amount=shipment_subtotal,
                    platform_fee=platform_commission,
                    seller_net_amount=seller_net,
                    status=EscrowHold.EscrowStatus.HELD,
                )

                # Initialize First Tracking Event
                TrackingEvent.objects.create(
                    shipment=shipment,
                    event_name="Order Placed & Processing",
                    location=city or "Dhaka Central Processing",
                )

            # Clear cart
            if request.user.is_authenticated:
                CartItem.objects.filter(cart__user=request.user).delete()
            else:
                request.session["cart_items"] = []
                request.session.modified = True

        return redirect("order_detail", id=order.id)

    return render(
        request,
        "orders/checkout.html",
        {
            "items": items,
            "subtotal": subtotal,
            "shipping_fee": shipping_fee,
            "total": total,
            "cart_count": cart_count,
            "default_address": default_address,
        },
    )


def order_detail_view(request, id):
    """
    Renders the Order Confirmation & Detail page with status timeline,
    shipments, seller consignment tracking, receipt breakdown, and cancellation option.
    """
    order = get_object_or_404(
        Order.objects.prefetch_related(
            "shipments__items__listing__book__authors",
            "shipments__seller",
        ),
        id=id,
    )
    _, _, cart_count = get_cart_items_for_request(request)

    # Determine if buyer can cancel order before shipment
    can_cancel = False
    if request.user.is_authenticated and order.buyer == request.user:
        if order.status not in [Order.Status.CANCELLED, Order.Status.COMPLETED]:
            can_cancel = all(
                s.status == OrderShipment.ShipmentStatus.WAITING_SELLER
                for s in order.shipments.all()
            )

    return render(
        request,
        "orders/order_detail.html",
        {
            "order": order,
            "cart_count": cart_count,
            "can_cancel": can_cancel,
        },
    )


def cancel_order_view(request, id):
    """
    Allows a buyer to cancel their order BEFORE the seller ships / dispatches it.
    - Validates order ownership and shipment status (must still be WAITING_SELLER).
    - Sets order and shipments to CANCELLED.
    - Restores physical book listings back to ACTIVE so other buyers can purchase.
    - Refunds held escrow funds.
    - Adds a tracking event and notifies the seller in conversation chat.
    """
    if not request.user.is_authenticated:
        messages.warning(request, "Please log in to manage your order.")
        return redirect("login")

    order = get_object_or_404(
        Order.objects.prefetch_related("shipments__items__listing__book", "shipments__escrow"),
        id=id,
        buyer=request.user,
    )

    if order.status == Order.Status.CANCELLED:
        messages.info(request, "This order has already been cancelled.")
        return redirect("order_detail", id=order.id)

    # Check that all shipments are still waiting for seller dispatch
    cannot_cancel = False
    for s in order.shipments.all():
        if s.status != OrderShipment.ShipmentStatus.WAITING_SELLER:
            cannot_cancel = True
            break

    if cannot_cancel:
        messages.error(
            request,
            "Cannot cancel order: One or more shipments have already been dispatched or picked up by the courier."
        )
        return redirect("order_detail", id=order.id)

    with transaction.atomic():
        order.status = Order.Status.CANCELLED
        order.save(update_fields=["status"])

        for shipment in order.shipments.all():
            shipment.status = OrderShipment.ShipmentStatus.CANCELLED
            shipment.save(update_fields=["status"])

            # Log tracking audit event
            TrackingEvent.objects.create(
                shipment=shipment,
                event_name="Order Cancelled by Buyer",
                location="Customer Request",
                raw_payload={"reason": "Buyer cancelled order before dispatch"},
            )

            # Restore physical book listing status to ACTIVE
            for item in shipment.items.all():
                listing = item.listing
                listing.status = BookListing.Status.ACTIVE
                listing.save(update_fields=["status"])

                # Post notification in inquiry chat
                from apps.messaging.models import Conversation, InquiryMessage
                conv = Conversation.objects.filter(listing=listing, buyer=request.user).first()
                if conv:
                    InquiryMessage.objects.create(
                        conversation=conv,
                        sender=request.user,
                        text=f"⚠️ Order Update: Buyer cancelled Order #{str(order.id)[:8]} before shipment dispatch. Listing is now restored to active store catalog.",
                    )

            # Refund Escrow Hold
            if hasattr(shipment, "escrow"):
                escrow = shipment.escrow
                escrow.status = EscrowHold.EscrowStatus.REFUNDED
                escrow.save(update_fields=["status"])

        # Refund Payment object if exists
        if hasattr(order, "payment"):
            payment = order.payment
            payment.status = Payment.Status.REFUNDED
            payment.save(update_fields=["status"])

    messages.success(request, f"Order #{str(order.id)[:8]} has been cancelled successfully. Your copy has been released and escrow refunded.")
    return redirect("order_detail", id=order.id)
