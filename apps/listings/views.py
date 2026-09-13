from decimal import Decimal
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

        return get_available_listings(
            book_slug=params.get("book_slug", ""),
            condition=params.get("condition", ""),
            min_price=min_p,
            max_price=max_p,
            is_hardcover=hardcover,
        )

    def perform_create(self, serializer: BookListingWriteSerializer) -> None:
        user = self.request.user
        if not getattr(user, "is_seller", False):
            raise PermissionDenied("Only registered sellers can list books for sale.")
        serializer.save(seller=user)


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

    def perform_destroy(self, instance: BookListing) -> None:
        if instance.seller != self.request.user and not self.request.user.is_staff:
            raise PermissionDenied("You do not possess permission to delete this listing.")
        instance.soft_delete()


class ListingImageUploadView(generics.CreateAPIView):
    serializer_class = ListingImageSerializer
    permission_classes = (permissions.IsAuthenticated,)
    parser_classes = (MultiPartParser, FormParser)

    def create(self, request: Request, *args, **kwargs) -> Response:
        listing_id = kwargs.get("listing_id")
        try:
            listing = BookListing.objects.get(id=listing_id, is_deleted=False)
        except BookListing.DoesNotExist:
            return Response({"error": "Listing not found."}, status=status.HTTP_404_NOT_FOUND)

        if listing.seller != request.user and not request.user.is_staff:
            raise PermissionDenied("You can only upload images for your own listings.")

        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        img_instance: ListingImage = serializer.save(listing=listing)

        # Trigger async WebP compression via Celery
        process_listing_image_to_webp.delay(img_instance.id)

        return Response(ListingImageSerializer(img_instance).data, status=status.HTTP_201_CREATED)


class SellerMyListingsView(generics.ListAPIView):
    serializer_class = BookListingReadSerializer
    permission_classes = (permissions.IsAuthenticated,)

    def get_queryset(self):
        return get_seller_listings(self.request.user.id)
