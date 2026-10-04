from decimal import Decimal
import uuid
from django.conf import settings
from django.db import models
from apps.listings.models import BookListing
from apps.orders.storage import PrivateEvidenceStorage


class Cart(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="cart")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self) -> str:
        return f"Cart of {self.user.email}"


class CartItem(models.Model):
    cart = models.ForeignKey(Cart, on_delete=models.CASCADE, related_name="items")
    listing = models.ForeignKey(BookListing, on_delete=models.CASCADE, related_name="cart_items")
    added_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-added_at"]
        constraints = [models.UniqueConstraint(fields=["cart", "listing"], name="unique_cart_listing")]

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
        CANCELLED = "CANCELLED", "Cancelled"

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


class PurchaseAgreement(models.Model):
    """Pickup lifecycle separate from chat and historical courier orders."""
    class Status(models.TextChoices):
        REQUESTED = "REQUESTED", "Requested"
        RESERVED = "RESERVED", "Reserved"
        PICKUP_AGREED = "PICKUP_AGREED", "Pickup agreed"
        AWAITING_CONFIRMATION = "AWAITING_CONFIRMATION", "Awaiting confirmation"
        COMPLETED = "COMPLETED", "Completed"
        CANCELLED = "CANCELLED", "Cancelled"
        DECLINED = "DECLINED", "Declined"
        EXPIRED = "EXPIRED", "Expired"
        DISPUTED = "DISPUTED", "Disputed"
    conversation = models.ForeignKey("messaging.Conversation", on_delete=models.PROTECT, related_name="agreements")
    listing = models.ForeignKey(BookListing, on_delete=models.PROTECT, related_name="agreements")
    buyer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="pickup_purchases")
    seller = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="pickup_sales")
    offer_proposed_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.PROTECT, related_name="proposed_offers")
    cancellation_reason = models.CharField(max_length=255, blank=True)
    offered_price = models.DecimalField(max_digits=8, decimal_places=2)
    accepted_price = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)
    status = models.CharField(max_length=24, choices=Status.choices, default=Status.REQUESTED, db_index=True)
    reservation_expires_at = models.DateTimeField(null=True, blank=True, db_index=True)
    pickup_place = models.CharField(max_length=255, blank=True)
    pickup_instructions = models.TextField(blank=True)
    pickup_at = models.DateTimeField(null=True, blank=True)
    pickup_latitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    pickup_longitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    pickup_proposed_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.PROTECT, related_name="pickup_proposals")
    pickup_accepted_at = models.DateTimeField(null=True, blank=True)
    buyer_confirmed_at = models.DateTimeField(null=True, blank=True)
    seller_confirmed_at = models.DateTimeField(null=True, blank=True)
    problem_details = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.CheckConstraint(condition=models.Q(offered_price__gt=0), name="positive_offer"),
            models.CheckConstraint(condition=models.Q(accepted_price__isnull=True) | models.Q(accepted_price__gt=0), name="positive_accepted_price"),
            models.UniqueConstraint(fields=["listing"], condition=models.Q(status__in=["RESERVED", "PICKUP_AGREED", "AWAITING_CONFIRMATION", "DISPUTED"]), name="one_live_pickup_per_copy"),
        ]


class SellerReview(models.Model):
    agreement = models.OneToOneField(PurchaseAgreement, on_delete=models.PROTECT, related_name="seller_review")
    rating = models.PositiveSmallIntegerField()
    condition_accuracy_rating = models.PositiveSmallIntegerField(null=True, blank=True)
    punctuality_rating = models.PositiveSmallIntegerField(null=True, blank=True)
    comment = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    class Meta:
        constraints = [models.CheckConstraint(condition=models.Q(rating__gte=1, rating__lte=5), name="seller_review_rating_range")]


class MarketplaceReport(models.Model):
    class Status(models.TextChoices):
        PENDING = "PENDING", "Pending"
        RESOLVED = "RESOLVED", "Resolved"
        DISMISSED = "DISMISSED", "Dismissed"
    reporter = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="marketplace_reports")
    listing = models.ForeignKey(BookListing, on_delete=models.PROTECT, related_name="reports")
    agreement = models.ForeignKey(PurchaseAgreement, null=True, blank=True, on_delete=models.PROTECT, related_name="reports")
    reported_user = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.PROTECT, related_name="received_marketplace_reports")
    evidence = models.FileField(storage=PrivateEvidenceStorage(), upload_to="reports/", blank=True)
    details = models.TextField()
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.PENDING)
    resolution = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)


class MarketplaceNotification(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="marketplace_notifications")
    conversation = models.ForeignKey("messaging.Conversation", on_delete=models.CASCADE, null=True, blank=True)
    email_sent_at = models.DateTimeField(null=True, blank=True)
    sms_sent_at = models.DateTimeField(null=True, blank=True)
    delivery_attempts = models.PositiveIntegerField(default=0)
    last_delivery_error = models.CharField(max_length=255, blank=True)
    text = models.CharField(max_length=255)
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    class Meta:
        ordering = ["-created_at"]


class ModerationAction(models.Model):
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="moderation_actions")
    report = models.ForeignKey(MarketplaceReport, on_delete=models.PROTECT, related_name="actions")
    action = models.CharField(max_length=20)
    reason = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
