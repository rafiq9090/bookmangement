from rest_framework import serializers
from apps.payments.models import EscrowHold, Payment, PayoutBatch, SellerLedger


class PaymentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Payment
        fields = ("id", "order", "gateway", "transaction_id", "amount", "status", "created_at")


class EscrowHoldSerializer(serializers.ModelSerializer):
    class Meta:
        model = EscrowHold
        fields = (
            "id",
            "order",
            "shipment",
            "gross_amount",
            "platform_fee",
            "seller_net_amount",
            "status",
            "released_at",
            "created_at",
        )


class SellerLedgerSerializer(serializers.ModelSerializer):
    class Meta:
        model = SellerLedger
        fields = ("id", "entry_type", "amount", "reference_id", "created_at")


class PayoutBatchSerializer(serializers.ModelSerializer):
    class Meta:
        model = PayoutBatch
        fields = ("id", "amount", "payout_method", "account_details", "status", "created_at", "processed_at")
        read_only_fields = ("id", "status", "created_at", "processed_at")
