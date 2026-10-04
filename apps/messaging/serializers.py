from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers
from config.security import clean_image
from django.core.exceptions import ValidationError
from apps.messaging.models import Conversation, InquiryMessage


class InquiryMessageSerializer(serializers.ModelSerializer):
    text = serializers.CharField(max_length=5000, required=True)
    def validate_photo_evidence(self, value):
        if value is None:
            return value
        try:
            return clean_image(value)
        except ValidationError as exc:
            raise serializers.ValidationError(exc.messages)

    sender_email = serializers.EmailField(source="sender.email", read_only=True)

    class Meta:
        model = InquiryMessage
        fields = ("id", "sender_email", "text", "photo_evidence", "is_read", "created_at")
        read_only_fields = ("id", "sender_email", "is_read", "created_at")


class ConversationCreateSerializer(serializers.Serializer):
    listing_id = serializers.IntegerField(min_value=1)
    message = serializers.CharField(max_length=5000, required=False, allow_blank=True)


class ConversationSerializer(serializers.ModelSerializer):
    messages = serializers.SerializerMethodField()

    @extend_schema_field(InquiryMessageSerializer(many=True))
    def get_messages(self, obj):
        recent = list(reversed(obj.messages.select_related("sender").order_by("-id")[:200]))
        return InquiryMessageSerializer(recent, many=True).data
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
            "order_status",
            "confirmed_price",
            "confirmed_at",
            "messages",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("id", "confirmed_at", "created_at", "updated_at")
