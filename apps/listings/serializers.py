from rest_framework import serializers
from config.security import clean_image
from django.core.exceptions import ValidationError
from apps.books.serializers import BookSerializer
from apps.listings.models import BookListing, ListingImage


class ListingImageSerializer(serializers.ModelSerializer):
    def validate_image(self, value):
        if value.size > 10 * 1024 * 1024:
            raise serializers.ValidationError("Photo must be at most 10 MB.")
        try:
            return clean_image(value)
        except ValidationError as exc:
            raise serializers.ValidationError(exc.messages)

    class Meta:
        model = ListingImage
        fields = ("id", "image", "webp_image", "caption", "is_primary", "uploaded_at")
        read_only_fields = ("id", "webp_image", "uploaded_at")


class BookListingReadSerializer(serializers.ModelSerializer):
    book = BookSerializer(read_only=True)
    images = ListingImageSerializer(many=True, read_only=True)
    seller_name = serializers.CharField(source="seller.seller_profile.store_name", read_only=True)
    seller_rating = serializers.DecimalField(
        source="seller.seller_profile.rating_avg", max_digits=3, decimal_places=2, read_only=True
    )

    class Meta:
        model = BookListing
        fields = (
            "id",
            "book",
            "seller_name",
            "seller_rating",
            "condition",
            "condition_notes",
            "district", "area", "latitude", "longitude", "is_collectible", "condition_needs_review",
            "price",
            "original_mrp",
            "edition_year",
            "is_hardcover",
            "has_dust_jacket",
            "is_signed_by_author",
            "status",
            "images",
            "created_at",
        )


class BookListingWriteSerializer(serializers.ModelSerializer):
    class Meta:
        model = BookListing
        fields = (
            "id",
            "book",
            "condition",
            "condition_notes",
            "district", "area", "latitude", "longitude", "is_collectible", "condition_needs_review",
            "price",
            "original_mrp",
            "edition_year",
            "is_hardcover",
            "has_dust_jacket",
            "is_signed_by_author",
        )

    def get_fields(self):
        fields = super().get_fields()
        fields["condition_needs_review"].read_only = True
        return fields

    def validate(self, attrs):
        from apps.listings.forms import ListingLocationForm
        instance = self.instance
        data = {field: attrs.get(field, getattr(instance, field, None)) for field in ("district", "area", "latitude", "longitude", "is_collectible")}
        form = ListingLocationForm(data)
        if not form.is_valid():
            raise serializers.ValidationError(form.errors)
        attrs.update(form.cleaned_data)
        return attrs

    def validate_price(self, value):
        if value <= 0:
            raise serializers.ValidationError("Price must be greater than zero.")
        return value
