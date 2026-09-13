from rest_framework import serializers
from .models import Address, CustomUser, SellerProfile


class UserRegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, min_length=8)

    class Meta:
        model = CustomUser
        fields = ("id", "email", "first_name", "last_name", "phone_number", "password")

    def create(self, validated_data: dict) -> CustomUser:
        return CustomUser.objects.create_user(**validated_data)


class UserProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = CustomUser
        fields = ("id", "email", "first_name", "last_name", "phone_number", "is_seller", "avatar", "created_at")
        read_only_fields = ("id", "email", "is_seller", "created_at")


class SellerProfileSerializer(serializers.ModelSerializer):
    user_email = serializers.EmailField(source="user.email", read_only=True)

    class Meta:
        model = SellerProfile
        fields = (
            "id",
            "user_email",
            "store_name",
            "bio",
            "kyc_status",
            "national_id_number",
            "payout_method",
            "payout_account_details",
            "rating_avg",
            "rating_count",
        )
        read_only_fields = ("id", "user_email", "kyc_status", "rating_avg", "rating_count")


class AddressSerializer(serializers.ModelSerializer):
    class Meta:
        model = Address
        fields = (
            "id",
            "recipient_name",
            "phone_number",
            "street_address",
            "city",
            "state_division",
            "postal_code",
            "country",
            "is_default",
            "created_at",
        )
        read_only_fields = ("id", "created_at")
