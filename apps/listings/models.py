from decimal import Decimal
from django.conf import settings
from django.db import models
from django.urls import reverse
from apps.books.models import Book


class BookListing(models.Model):
    """
    Represents a specific physical copy of a book put on sale by a seller.
    Enforces condition grading, physical defect descriptions, and lifecycle states.
    """

    class Condition(models.TextChoices):
        LIKE_NEW = "LIKE_NEW", "Like New (Minimal signs of wear)"
        VERY_GOOD = "VERY_GOOD", "Very Good (Clean pages, light spine creasing)"
        GOOD = "GOOD", "Good (Average used wear, possible notes/highlights)"
        ACCEPTABLE = "ACCEPTABLE", "Acceptable (Readable copy, noticeable wear or damage)"
        COLLECTIBLE = "COLLECTIBLE", "Collectible / Vintage (Rare edition, signed)"

    class Status(models.TextChoices):
        DRAFT = "DRAFT", "Draft"
        ACTIVE = "ACTIVE", "Active / Available"
        RESERVED = "RESERVED", "Reserved (Checkout in progress)"
        SOLD = "SOLD", "Sold"
        ARCHIVED = "ARCHIVED", "Archived / Deactivated"

    book = models.ForeignKey(
        Book,
        on_delete=models.CASCADE,
        related_name="listings",
        help_text="The canonical book record.",
    )
    seller = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="book_listings",
    )
    condition = models.CharField(
        max_length=20,
        choices=Condition.choices,
        default=Condition.GOOD,
        db_index=True,
    )
    condition_notes = models.TextField(
        blank=True,
        help_text="Specific wear details: markings, tears, yellowed pages, bindings.",
    )
    price = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        help_text="Listing price in platform currency.",
    )
    original_mrp = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Original printed cover price (for comparison).",
    )
    edition_year = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text="Year this specific physical copy was printed.",
    )
    is_hardcover = models.BooleanField(default=False)
    has_dust_jacket = models.BooleanField(default=False)
    is_signed_by_author = models.BooleanField(default=False)
    
    status = models.CharField(
        max_length=15,
        choices=Status.choices,
        default=Status.ACTIVE,
        db_index=True,
    )
    is_deleted = models.BooleanField(default=False, db_index=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Book Listing"
        verbose_name_plural = "Book Listings"
        indexes = [
            models.Index(fields=["status", "condition", "price"]),
            models.Index(fields=["seller", "status"]),
        ]

    def __str__(self) -> str:
        return f"[{self.get_condition_display()}] {self.book.title} - ৳{self.price} by {self.seller.email}"

    def soft_delete(self) -> None:
        self.is_deleted = True
        self.status = self.Status.ARCHIVED
        self.save(update_fields=["is_deleted", "status", "updated_at"])


class ListingImage(models.Model):
    listing = models.ForeignKey(BookListing, on_delete=models.CASCADE, related_name="images")
    image = models.ImageField(upload_to="listing_photos/%Y/%m/")
    webp_image = models.ImageField(upload_to="listing_photos/webp/%Y/%m/", blank=True, null=True)
    caption = models.CharField(max_length=100, blank=True)
    is_primary = models.BooleanField(default=False)
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-is_primary", "uploaded_at"]
        verbose_name = "Listing Image"
        verbose_name_plural = "Listing Images"

    def __str__(self) -> str:
        return f"Image for listing #{self.listing_id}"
