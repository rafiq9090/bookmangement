from decimal import Decimal
import uuid
from django.conf import settings
from django.db import models
from apps.listings.models import BookListing


class Cart(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="cart")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self) -> str:
        return f"Cart of {self.user.email}"


class CartItem(models.Model):
    cart = models.ForeignKey(Cart, on_delete=models.CASCADE, related_name="items")
    listing = models.OneToOneField(BookListing, on_delete=models.CASCADE, related_name="cart_item")
    added_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-added_at"]

    def __str__(self) -> str:
        return f"{self.listing.book.title} in {self.cart.user.email}'s cart"


class Order(models.Model):
    """
    Global order invoice aggregating multiple seller shipments into one single checkout payment.
    """

    class Status(models.TextChoices):
        PENDING = "PENDING", "Pending Payment"
        PAID = "PAID", "Paid & Escrow Held"
        PROCESSING = "PROCESSING", "In Progress"
        COMPLETED = "COMPLETED", "All Shipments Delivered"
        CANCELLED = "CANCELLED", "Cancelled"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    buyer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="orders",
    )
    shipping_address_snapshot = models.JSONField(
        default=dict,
        help_text="Immutable snapshot of shipping details at the moment of purchase.",
    )
    total_amount = models.DecimalField(max_digits=10, decimal_places=2)
    shipping_total = models.DecimalField(max_digits=8, decimal_places=2, default=Decimal("0.00"))
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
        db_index=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Order"
        verbose_name_plural = "Orders"

    def __str__(self) -> str:
        return f"Order #{str(self.id)[:8]} - {self.buyer.email} (৳{self.total_amount})"


class OrderShipment(models.Model):
    """
    Sub-order isolating courier delivery, tracking, and seller payout.
    Each seller fulfilling an order receives their own dedicated OrderShipment.
    """

    class ShipmentStatus(models.TextChoices):
        WAITING_SELLER = "WAITING", "Waiting for Seller Dispatch"
        PICKED_UP = "PICKED_UP", "Picked Up by Courier"
        IN_TRANSIT = "IN_TRANSIT", "In Transit"
        DELIVERED = "DELIVERED", "Delivered"
        RETURNED = "RETURNED", "Returned / Disputed"

    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="shipments")
    seller = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="seller_shipments",
    )
    courier_name = models.CharField(max_length=50, blank=True)
    tracking_number = models.CharField(max_length=100, blank=True, db_index=True)
    shipping_fee = models.DecimalField(max_digits=7, decimal_places=2, default=Decimal("60.00"))
    subtotal = models.DecimalField(max_digits=9, decimal_places=2)
    status = models.CharField(
        max_length=20,
        choices=ShipmentStatus.choices,
        default=ShipmentStatus.WAITING_SELLER,
        db_index=True,
    )
    dispatched_at = models.DateTimeField(null=True, blank=True)
    delivered_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Order Shipment"
        verbose_name_plural = "Order Shipments"

    def __str__(self) -> str:
        return f"Shipment #{self.id} for Seller {self.seller.email} (Order #{str(self.order_id)[:8]})"


class OrderItem(models.Model):
    """Specific physical book attached to a shipment."""
    shipment = models.ForeignKey(OrderShipment, on_delete=models.CASCADE, related_name="items")
    listing = models.ForeignKey(BookListing, on_delete=models.PROTECT, related_name="order_items")
    price_at_purchase = models.DecimalField(max_digits=8, decimal_places=2)

    class Meta:
        verbose_name = "Order Item"
        verbose_name_plural = "Order Items"

    def __str__(self) -> str:
        return f"{self.listing.book.title} (৳{self.price_at_purchase})"
