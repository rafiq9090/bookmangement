from decimal import Decimal
from django.db import transaction
from rest_framework import generics, permissions, status
from rest_framework.exceptions import PermissionDenied
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.request import Request
from rest_framework.response import Response

from apps.listings.models import BookListing, ListingImage
from apps.listings.selectors import get_available_listings, get_seller_listings
from apps.listings.serializers import (
    BookListingReadSerializer,
    BookListingWriteSerializer,
    ListingImageSerializer,
)
from apps.listings.tasks import process_listing_image_to_webp


class ListingListCreateView(generics.ListCreateAPIView):
    permission_classes = (permissions.IsAuthenticatedOrReadOnly,)

    def get_serializer_class(self):
        if self.request.method == "POST":
            return BookListingWriteSerializer
        return BookListingReadSerializer

    def get_queryset(self):
        params = self.request.query_params
        min_p = Decimal(params["min_price"]) if "min_price" in params and params["min_price"].isdigit() else None
        max_p = Decimal(params["max_price"]) if "max_price" in params and params["max_price"].isdigit() else None
        hardcover = params.get("is_hardcover", "").lower() == "true" if "is_hardcover" in params else None

        queryset = get_available_listings(
            book_slug=params.get("book_slug", ""),
            condition=params.get("condition", ""),
            min_price=min_p,
            max_price=max_p,
            is_hardcover=hardcover,
        )

        for field in ("district", "area"):
            if params.get(field):
                queryset = queryset.filter(**{field + "__iexact": params[field]})
        return queryset

    def perform_create(self, serializer: BookListingWriteSerializer) -> None:
        user = self.request.user
        serializer.save(seller=user, status=BookListing.Status.DRAFT)
        if not user.is_seller:
            user.is_seller = True
            user.save(update_fields=["is_seller"])


class ListingDetailView(generics.RetrieveUpdateDestroyAPIView):
    permission_classes = (permissions.IsAuthenticatedOrReadOnly,)

    def get_serializer_class(self):
        if self.request.method in ("PUT", "PATCH"):
            return BookListingWriteSerializer
        return BookListingReadSerializer

    def get_queryset(self):
        return BookListing.objects.filter(is_deleted=False).select_related(
            "book", "seller", "seller__seller_profile"
        ).prefetch_related("images")

    @transaction.atomic
    def perform_update(self, serializer):
        listing = BookListing.objects.select_for_update().get(pk=serializer.instance.pk)
        serializer.instance = listing
        if listing.seller_id != self.request.user.pk:
            raise PermissionDenied("Only the owner can edit this copy.")
        if listing.status in (BookListing.Status.RESERVED, BookListing.Status.SOLD):
            raise PermissionDenied("Reserved or sold copies cannot be edited.")
        serializer.save(condition_needs_review=False)

    @transaction.atomic
    def perform_destroy(self, instance: BookListing) -> None:
        instance = BookListing.objects.select_for_update().get(pk=instance.pk)
        if instance.seller != self.request.user and not self.request.user.is_staff:
            raise PermissionDenied("You do not possess permission to delete this listing.")
        if instance.status in (BookListing.Status.RESERVED, BookListing.Status.SOLD):
            raise PermissionDenied("Reserved or sold copies cannot be deleted.")
        instance.soft_delete()


class ListingImageUploadView(generics.CreateAPIView):
    serializer_class = ListingImageSerializer
    permission_classes = (permissions.IsAuthenticated,)
    parser_classes = (MultiPartParser, FormParser)

    @transaction.atomic
    def create(self, request: Request, *args, **kwargs) -> Response:
        listing_id = kwargs.get("listing_id")
        try:
            listing = BookListing.objects.select_for_update().get(id=listing_id, is_deleted=False)
        except BookListing.DoesNotExist:
            return Response({"error": "Listing not found."}, status=status.HTTP_404_NOT_FOUND)

        if listing.seller != request.user and not request.user.is_staff:
            raise PermissionDenied("You can only upload images for your own listings.")

        if listing.status in (BookListing.Status.RESERVED, BookListing.Status.SOLD):
            raise PermissionDenied("Cannot change photos during or after a purchase.")
        if listing.images.count() >= 5:
            from rest_framework.exceptions import ValidationError
            raise ValidationError("A copy can have at most five photos.")
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        img_instance: ListingImage = serializer.save(listing=listing)

        # First actual-copy photo publishes an API-created draft.
        if listing.status == BookListing.Status.DRAFT and listing.district and listing.area and not listing.condition_needs_review:
            listing.status = BookListing.Status.ACTIVE
            listing.save(update_fields=["status", "updated_at"])
        from apps.listings.tasks import queue_listing_image
        transaction.on_commit(lambda: queue_listing_image(img_instance.id))

        return Response(ListingImageSerializer(img_instance).data, status=status.HTTP_201_CREATED)


class SellerMyListingsView(generics.ListAPIView):
    serializer_class = BookListingReadSerializer
    permission_classes = (permissions.IsAuthenticated,)

    def get_queryset(self):
        return get_seller_listings(self.request.user.id)
