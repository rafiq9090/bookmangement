from drf_spectacular.utils import extend_schema
from rest_framework import generics, permissions, status
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.listings.models import BookListing
from apps.orders.models import Cart, CartItem, Order, OrderShipment
from apps.orders.serializers import (
    CartItemSerializer,
    CartSerializer,
    CheckoutRequestSerializer,
    OrderSerializer,
    OrderShipmentSerializer,
)
from apps.orders.services.checkout import process_cart_checkout


class CartView(APIView):
    permission_classes = (permissions.IsAuthenticated,)

    @extend_schema(responses={200: CartSerializer})
    def get(self, request: Request) -> Response:
        cart, _ = Cart.objects.prefetch_related("items__listing__book").get_or_create(user=request.user)
        return Response(CartSerializer(cart).data)

    @extend_schema(request=CartItemSerializer, responses={201: CartItemSerializer})
    def post(self, request: Request) -> Response:
        listing_id = request.data.get("listing_id")
        try:
            listing = BookListing.objects.get(id=listing_id, status=BookListing.Status.ACTIVE, is_deleted=False)
        except BookListing.DoesNotExist:
            return Response({"error": "Listing is not available."}, status=status.HTTP_404_NOT_FOUND)

        if listing.seller == request.user:
            return Response({"error": "Cannot add your own listing to cart."}, status=status.HTTP_400_BAD_REQUEST)

        cart, _ = Cart.objects.get_or_create(user=request.user)
        item, created = CartItem.objects.get_or_create(cart=cart, listing=listing)

        return Response(CartItemSerializer(item).data, status=status.HTTP_201_CREATED)

    @extend_schema(responses={204: None})
    def delete(self, request: Request) -> Response:
        listing_id = request.data.get("listing_id")
        CartItem.objects.filter(cart__user=request.user, listing_id=listing_id).delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class CheckoutView(APIView):
    permission_classes = (permissions.IsAuthenticated,)

    @extend_schema(request=CheckoutRequestSerializer, responses={201: OrderSerializer})
    def post(self, request: Request) -> Response:
        serializer = CheckoutRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        order = process_cart_checkout(
            buyer=request.user,
            shipping_address_data=serializer.validated_data,
        )
        return Response(OrderSerializer(order).data, status=status.HTTP_201_CREATED)


class OrderListView(generics.ListAPIView):
    serializer_class = OrderSerializer
    permission_classes = (permissions.IsAuthenticated,)

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return Order.objects.none()
        return (
            Order.objects.filter(buyer=self.request.user)
            .prefetch_related("shipments__items__listing__book")
            .order_by("-created_at")
        )


class OrderDetailView(generics.RetrieveAPIView):
    serializer_class = OrderSerializer
    permission_classes = (permissions.IsAuthenticated,)
    lookup_field = "id"

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return Order.objects.none()
        return Order.objects.filter(buyer=self.request.user).prefetch_related(
            "shipments__items__listing__book"
        )


class SellerShipmentListView(generics.ListAPIView):
    serializer_class = OrderShipmentSerializer
    permission_classes = (permissions.IsAuthenticated,)

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return OrderShipment.objects.none()
        return (
            OrderShipment.objects.filter(seller=self.request.user)
            .prefetch_related("items__listing__book")
            .order_by("-created_at")
        )
