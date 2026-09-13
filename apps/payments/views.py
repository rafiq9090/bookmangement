from decimal import Decimal
from django.db.models import Sum
from drf_spectacular.utils import extend_schema, inline_serializer
from rest_framework import generics, permissions, serializers as drf_serializers, status
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.orders.models import Order
from apps.payments.gateways.sslcommerz import SSLCommerzGateway
from apps.payments.models import Payment, PayoutBatch, SellerLedger
from apps.payments.serializers import (
    PaymentSerializer,
    PayoutBatchSerializer,
    SellerLedgerSerializer,
)
from apps.payments.services.ledger import confirm_payment_and_finalize_order


class InitiatePaymentView(APIView):
    permission_classes = (permissions.IsAuthenticated,)

    @extend_schema(
        request=None,
        responses={
            200: inline_serializer(
                name="PaymentInitiationResponse",
                fields={"payment_url": drf_serializers.URLField()},
            )
        },
    )
    def post(self, request: Request, order_id: str) -> Response:
        try:
            order = Order.objects.get(id=order_id, buyer=request.user)
        except Order.DoesNotExist:
            return Response({"error": "Order not found."}, status=status.HTTP_404_NOT_FOUND)

        if order.status != Order.Status.PENDING:
            return Response({"error": "Order has already been processed or paid."}, status=status.HTTP_400_BAD_REQUEST)

        gateway = SSLCommerzGateway()
        redirect_base = request.build_absolute_uri("/api/v1/payments/sslcommerz")
        result = gateway.initiate_payment(order=order, redirect_url=redirect_base)

        if result.get("status") == "SUCCESS":
            return Response({"payment_url": result.get("gateway_url")})
        return Response({"error": result.get("message")}, status=status.HTTP_502_BAD_GATEWAY)


class PaymentWebhookView(APIView):
    """
    Public webhook receiver invoked by payment gateways upon successful user authorization.
    """
    permission_classes = (permissions.AllowAny,)

    @extend_schema(
        request=inline_serializer(
            name="PaymentWebhookRequest",
            fields={
                "tran_id": drf_serializers.CharField(),
                "val_id": drf_serializers.CharField(required=False),
                "bank_tran_id": drf_serializers.CharField(required=False),
            },
        ),
        responses={200: PaymentSerializer},
    )
    def post(self, request: Request) -> Response:
        data = request.data
        tran_id = data.get("tran_id")
        if not tran_id:
            return Response({"error": "Missing transaction id."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            order = Order.objects.get(id=tran_id)
        except Order.DoesNotExist:
            return Response({"error": "Order not found."}, status=status.HTTP_404_NOT_FOUND)

        gateway = SSLCommerzGateway()
        is_valid = gateway.verify_payment(data)

        if not is_valid and not gateway.is_sandbox:
            return Response({"error": "Invalid gateway signature."}, status=status.HTTP_400_BAD_REQUEST)

        payment = confirm_payment_and_finalize_order(
            order=order,
            transaction_id=data.get("bank_tran_id", tran_id),
            gateway_name=Payment.Gateway.SSLCOMMERZ,
            raw_response=dict(data),
        )
        return Response(PaymentSerializer(payment).data, status=status.HTTP_200_OK)


class SellerBalanceView(APIView):
    permission_classes = (permissions.IsAuthenticated,)

    @extend_schema(
        responses={
            200: inline_serializer(
                name="SellerBalanceResponse",
                fields={"available_balance": drf_serializers.DecimalField(max_digits=10, decimal_places=2)},
            )
        }
    )
    def get(self, request: Request) -> Response:
        credits = (
            SellerLedger.objects.filter(
                seller=request.user,
                entry_type=SellerLedger.EntryType.SALE_CREDIT,
            ).aggregate(total=Sum("amount"))["total"]
            or Decimal("0.00")
        )

        debits = (
            SellerLedger.objects.filter(
                seller=request.user,
                entry_type__in=[SellerLedger.EntryType.PAYOUT_DEBIT, SellerLedger.EntryType.REFUND_DEBIT],
            ).aggregate(total=Sum("amount"))["total"]
            or Decimal("0.00")
        )

        available_balance = credits - debits
        return Response({"available_balance": str(available_balance)})


class SellerLedgerListView(generics.ListAPIView):
    serializer_class = SellerLedgerSerializer
    permission_classes = (permissions.IsAuthenticated,)

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return SellerLedger.objects.none()
        return SellerLedger.objects.filter(seller=self.request.user)


class RequestPayoutView(generics.CreateAPIView):
    serializer_class = PayoutBatchSerializer
    permission_classes = (permissions.IsAuthenticated,)

    def perform_create(self, serializer: PayoutBatchSerializer) -> None:
        serializer.save(seller=self.request.user)
