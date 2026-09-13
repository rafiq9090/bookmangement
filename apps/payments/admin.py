from django.contrib import admin
from apps.payments.models import EscrowHold, Payment, PayoutBatch, SellerLedger


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ("transaction_id", "order", "gateway", "amount", "status", "created_at")
    list_filter = ("status", "gateway")
    search_fields = ("transaction_id", "order__id")


@admin.register(EscrowHold)
class EscrowHoldAdmin(admin.ModelAdmin):
    list_display = ("id", "order", "shipment", "gross_amount", "platform_fee", "seller_net_amount", "status")
    list_filter = ("status",)
    search_fields = ("order__id", "shipment__id")


@admin.register(SellerLedger)
class SellerLedgerAdmin(admin.ModelAdmin):
    list_display = ("seller", "entry_type", "amount", "reference_id", "created_at")
    list_filter = ("entry_type",)
    search_fields = ("seller__email", "reference_id")


@admin.register(PayoutBatch)
class PayoutBatchAdmin(admin.ModelAdmin):
    list_display = ("id", "seller", "amount", "payout_method", "status", "created_at", "processed_at")
    list_filter = ("status", "payout_method")
