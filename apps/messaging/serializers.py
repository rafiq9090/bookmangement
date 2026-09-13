from rest_framework import serializers
from apps.messaging.models import Conversation, InquiryMessage


class InquiryMessageSerializer(serializers.ModelSerializer):
    sender_email = serializers.EmailField(source="sender.email", read_only=True)

    class Meta:
        model = InquiryMessage
        fields = ("id", "sender_email", "text", "photo_evidence", "is_read", "created_at")
        read_only_fields = ("id", "sender_email", "is_read", "created_at")


class ConversationSerializer(serializers.ModelSerializer):
    messages = InquiryMessageSerializer(many=True, read_only=True)
    book_title = serializers.CharField(source="listing.book.title", read_only=True)
    listing_price = serializers.DecimalField(
        source="listing.price", max_digits=8, decimal_places=2, read_only=True
    )
    buyer_email = serializers.EmailField(source="buyer.email", read_only=True)
    seller_store = serializers.CharField(source="seller.seller_profile.store_name", read_only=True)

    class Meta:
        model = Conversation
        fields = (
            "id",
            "listing",
            "book_title",
            "listing_price",
            "buyer_email",
            "seller_store",
            "messages",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("id", "created_at", "updated_at")
