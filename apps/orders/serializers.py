from rest_framework import serializers
from apps.listings.serializers import BookListingReadSerializer
from apps.orders.models import Cart, CartItem, Order, OrderItem, OrderShipment


class CartItemSerializer(serializers.ModelSerializer):
    listing = BookListingReadSerializer(read_only=True)
    listing_id = serializers.IntegerField(write_only=True)

    class Meta:
        model = CartItem
        fields = ("id", "listing", "listing_id", "added_at")


class CartSerializer(serializers.ModelSerializer):
    items = CartItemSerializer(many=True, read_only=True)
    total_price = serializers.SerializerMethodField()

    class Meta:
        model = Cart
        fields = ("id", "items", "total_price")

    def get_total_price(self, obj: Cart) -> str:
        total = sum(item.listing.price for item in obj.items.all())
        return str(total)


class OrderItemSerializer(serializers.ModelSerializer):
    book_title = serializers.CharField(source="listing.book.title", read_only=True)
    condition = serializers.CharField(source="listing.get_condition_display", read_only=True)

    class Meta:
        model = OrderItem
        fields = ("id", "book_title", "condition", "price_at_purchase")


class OrderShipmentSerializer(serializers.ModelSerializer):
    items = OrderItemSerializer(many=True, read_only=True)
    seller_store = serializers.CharField(source="seller.seller_profile.store_name", read_only=True)

    class Meta:
        model = OrderShipment
        fields = (
            "id",
            "seller_store",
            "courier_name",
            "tracking_number",
            "shipping_fee",
            "subtotal",
            "status",
            "items",
            "dispatched_at",
            "delivered_at",
        )


class OrderSerializer(serializers.ModelSerializer):
    shipments = OrderShipmentSerializer(many=True, read_only=True)

    class Meta:
        model = Order
        fields = (
            "id",
            "total_amount",
            "shipping_total",
            "status",
            "shipping_address_snapshot",
            "shipments",
            "created_at",
        )


class CheckoutRequestSerializer(serializers.Serializer):
    recipient_name = serializers.CharField(max_length=100)
    phone_number = serializers.CharField(max_length=20)
    street_address = serializers.CharField(max_length=255)
    city = serializers.CharField(max_length=100)
    state_division = serializers.CharField(max_length=100)
    postal_code = serializers.CharField(max_length=20)
    country = serializers.CharField(max_length=50, default="Bangladesh")
