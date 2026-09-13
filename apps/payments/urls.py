from django.urls import path
from apps.payments.views import (
    InitiatePaymentView,
    PaymentWebhookView,
    RequestPayoutView,
    SellerBalanceView,
    SellerLedgerListView,
)

app_name = "payments"

urlpatterns = [
    path("initiate/<uuid:order_id>/", InitiatePaymentView.as_view(), name="initiate"),
    path("sslcommerz/ipn/", PaymentWebhookView.as_view(), name="webhook-ipn"),
    path("sslcommerz/success/", PaymentWebhookView.as_view(), name="webhook-success"),
    path("balance/", SellerBalanceView.as_view(), name="balance"),
    path("ledger/", SellerLedgerListView.as_view(), name="ledger-history"),
    path("payout/request/", RequestPayoutView.as_view(), name="request-payout"),
]
