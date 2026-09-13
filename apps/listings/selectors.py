from decimal import Decimal
from django.db.models import QuerySet
from apps.listings.models import BookListing


def get_available_listings(
    book_slug: str = "",
    condition: str = "",
    min_price: Decimal | None = None,
    max_price: Decimal | None = None,
    is_hardcover: bool | None = None,
) -> QuerySet[BookListing]:
    """Retrieves active, unsold, unreserved used book listings."""
    queryset = (
        BookListing.objects.filter(
            status=BookListing.Status.ACTIVE,
            is_deleted=False,
        )
        .select_related("book", "seller", "seller__seller_profile")
        .prefetch_related("images", "book__authors")
    )

    if book_slug:
        queryset = queryset.filter(book__slug=book_slug)
    if condition:
        queryset = queryset.filter(condition=condition)
    if min_price is not None:
        queryset = queryset.filter(price__gte=min_price)
    if max_price is not None:
        queryset = queryset.filter(price__lte=max_price)
    if is_hardcover is not None:
        queryset = queryset.filter(is_hardcover=is_hardcover)

    return queryset


def get_seller_listings(seller_id: int) -> QuerySet[BookListing]:
    """Retrieves all listings owned by a specific seller, excluding soft-deleted items."""
    return (
        BookListing.objects.filter(seller_id=seller_id, is_deleted=False)
        .select_related("book")
        .prefetch_related("images")
    )
