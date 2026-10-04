from rest_framework import serializers
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from config.security import clean_image
from .models import Address, CustomUser, SellerProfile


class UserRegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, min_length=8)
    is_seller = serializers.BooleanField(default=False, required=False)

    class Meta:
        model = CustomUser
        fields = ("id", "email", "first_name", "last_name", "phone_number", "password", "is_seller")

    def validate(self, attrs):
        try:
            validate_password(attrs["password"], CustomUser(**{k: v for k, v in attrs.items() if k != "password"}))
        except ValidationError as exc:
            raise serializers.ValidationError({"password": exc.messages})
        return attrs

    def create(self, validated_data: dict) -> CustomUser:
        return CustomUser.objects.create_user(**validated_data)


class UserProfileSerializer(serializers.ModelSerializer):
    def validate_avatar(self, value):
        try:
            return clean_image(value)
        except ValidationError as exc:
            raise serializers.ValidationError(exc.messages)

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
