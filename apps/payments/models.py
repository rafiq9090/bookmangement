from decimal import Decimal
from django.conf import settings
from django.db import models
from apps.orders.models import Order, OrderShipment


class Payment(models.Model):
    class Gateway(models.TextChoices):
        SSLCOMMERZ = "SSLCOMMERZ", "SSLCommerz"
        STRIPE = "STRIPE", "Stripe"
        BKASH = "BKASH", "bKash Direct"

    class Status(models.TextChoices):
        INITIATED = "INITIATED", "Initiated"
        SUCCESS = "SUCCESS", "Payment Successful"
        FAILED = "FAILED", "Payment Failed"
        REFUNDED = "REFUNDED", "Refunded"

    order = models.OneToOneField(Order, on_delete=models.PROTECT, related_name="payment")
    gateway = models.CharField(max_length=20, choices=Gateway.choices, default=Gateway.SSLCOMMERZ)
    transaction_id = models.CharField(max_length=100, unique=True, db_index=True)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    status = models.CharField(max_length=15, choices=Status.choices, default=Status.INITIATED, db_index=True)
    raw_response = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Payment"
        verbose_name_plural = "Payments"

    def __str__(self) -> str:
        return f"Payment {self.transaction_id} ({self.status}) - ${self.amount}"


class EscrowHold(models.Model):
    """
    Retains funds in escrow per shipment until delivery is verified by courier or buyer.
    """

    class EscrowStatus(models.TextChoices):
        HELD = "HELD", "Funds Held in Escrow"
        RELEASED = "RELEASED", "Released to Seller Available Balance"
        REFUNDED = "REFUNDED", "Refunded to Buyer"
        DISPUTED = "DISPUTED", "Under Dispute"

    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="escrow_holds")
    shipment = models.OneToOneField(OrderShipment, on_delete=models.CASCADE, related_name="escrow")
    gross_amount = models.DecimalField(max_digits=10, decimal_places=2)
    platform_fee = models.DecimalField(max_digits=8, decimal_places=2)
    seller_net_amount = models.DecimalField(max_digits=10, decimal_places=2)
    status = models.CharField(
        max_length=15,
        choices=EscrowStatus.choices,
        default=EscrowStatus.HELD,
        db_index=True,
    )
    released_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Escrow Hold"
        verbose_name_plural = "Escrow Holds"

    def __str__(self) -> str:
        return f"Escrow #{self.id} for Shipment #{self.shipment_id} - ${self.seller_net_amount}"


class SellerLedger(models.Model):
    """Double-entry style financial records for seller payouts and fee deductions."""

    class EntryType(models.TextChoices):
        SALE_CREDIT = "SALE_CREDIT", "Sale Revenue"
        PLATFORM_FEE = "PLATFORM_FEE", "Platform Commission"
        PAYOUT_DEBIT = "PAYOUT_DEBIT", "Bank/MFS Withdrawal"
        REFUND_DEBIT = "REFUND_DEBIT", "Order Refund"

    seller = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="ledger_entries",
    )
    entry_type = models.CharField(max_length=15, choices=EntryType.choices)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    reference_id = models.CharField(max_length=120)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Seller Ledger"
        verbose_name_plural = "Seller Ledgers"

    def __str__(self) -> str:
        return f"{self.seller.email} | {self.entry_type} | ${self.amount}"


class PayoutBatch(models.Model):
    class Status(models.TextChoices):
        REQUESTED = "REQUESTED", "Requested"
        PROCESSING = "PROCESSING", "Processing"
        COMPLETED = "COMPLETED", "Completed"
        REJECTED = "REJECTED", "Rejected"

    seller = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="payout_requests",
    )
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    payout_method = models.CharField(max_length=20)
    account_details = models.CharField(max_length=120)
    status = models.CharField(max_length=15, choices=Status.choices, default=Status.REQUESTED)
    created_at = models.DateTimeField(auto_now_add=True)
    processed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Payout Batch"
        verbose_name_plural = "Payout Batches"
