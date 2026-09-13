from django.urls import path
from apps.orders.views import (
    CartView,
    CheckoutView,
    OrderDetailView,
    OrderListView,
    SellerShipmentListView,
)

app_name = "orders"

urlpatterns = [
    path("cart/", CartView.as_view(), name="cart"),
    path("checkout/", CheckoutView.as_view(), name="checkout"),
    path("", OrderListView.as_view(), name="order-list"),
    path("<uuid:id>/", OrderDetailView.as_view(), name="order-detail"),
    path("seller/shipments/", SellerShipmentListView.as_view(), name="seller-shipments"),
]
