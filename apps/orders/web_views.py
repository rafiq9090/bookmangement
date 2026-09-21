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


def cart_view(request):
    """
    Renders the Shopping Cart page with line items, condition badges,
    pricing, quantity summary, and estimated shipping.
    """
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
    Adds a book listing to the user's database or session cart.
    Supports optional redirect directly to checkout (e.g. Purchase Now).
    """
    listing = get_object_or_404(BookListing, id=listing_id, status=BookListing.Status.ACTIVE, is_deleted=False)
    if request.user.is_authenticated:
        cart, _ = Cart.objects.get_or_create(user=request.user)
        CartItem.objects.get_or_create(cart=cart, listing=listing)
    else:
        cart_ids = request.session.get("cart_items", [])
        if listing.id not in cart_ids:
            cart_ids.append(listing.id)
            request.session["cart_items"] = cart_ids
            request.session.modified = True

    if request.GET.get("redirect") == "checkout":
        return redirect("checkout")
    return redirect("cart")


def remove_from_cart_view(request, item_id):
    """
    Removes a book listing from the user's database or session cart.
    """
    if request.user.is_authenticated:
        CartItem.objects.filter(cart__user=request.user, id=item_id).delete()
    else:
        cart_ids = request.session.get("cart_items", [])
        if item_id in cart_ids:
            cart_ids.remove(item_id)
            request.session["cart_items"] = cart_ids
            request.session.modified = True
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
            order = Order.objects.create(
                buyer=buyer,
                shipping_address_snapshot=address_snapshot,
                total_amount=total,
                shipping_total=shipping_fee,
                status=Order.Status.PAID if payment_method in ["bkash", "nagad", "card"] else Order.Status.PENDING,
            )

            # Group items by seller
            seller_items_map = defaultdict(list)
            for it in items:
                seller_items_map[it["listing"].seller].append(it["listing"])

            for seller, listings in seller_items_map.items():
                shipment_subtotal = sum(l.price for l in listings)
                shipment = OrderShipment.objects.create(
                    order=order,
                    seller=seller,
                    shipping_fee=shipping_fee,
                    subtotal=shipment_subtotal,
                    courier_name="Steadfast Courier",
                    tracking_number=f"EB-{uuid.uuid4().hex[:8].upper()}",
                    status=OrderShipment.ShipmentStatus.WAITING_SELLER,
                )
                for l in listings:
                    OrderItem.objects.create(
                        shipment=shipment,
                        listing=l,
                        price_at_purchase=l.price,
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
    shipments, seller consignment tracking, and receipt breakdown.
    """
    order = get_object_or_404(
        Order.objects.prefetch_related("shipments__items__listing__book", "shipments__seller"),
        id=id,
    )
    _, _, cart_count = get_cart_items_for_request(request)

    return render(
        request,
        "orders/order_detail.html",
        {
            "order": order,
            "cart_count": cart_count,
        },
    )
