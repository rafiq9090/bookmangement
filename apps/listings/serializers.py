from rest_framework import serializers
from apps.books.serializers import BookSerializer
from apps.listings.models import BookListing, ListingImage


class ListingImageSerializer(serializers.ModelSerializer):
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
            "price",
            "original_mrp",
            "edition_year",
            "is_hardcover",
            "has_dust_jacket",
            "is_signed_by_author",
        )

    def validate_price(self, value):
        if value <= 0:
            raise serializers.ValidationError("Price must be greater than zero.")
        return value
