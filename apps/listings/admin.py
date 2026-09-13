from django.contrib import admin
from apps.listings.models import BookListing, ListingImage


class ListingImageInline(admin.TabularInline):
    model = ListingImage
    extra = 1


@admin.register(BookListing)
class BookListingAdmin(admin.ModelAdmin):
    list_display = ("book", "seller", "condition", "price", "status", "edition_year", "created_at")
    list_filter = ("status", "condition", "is_hardcover", "is_deleted")
    search_fields = ("book__title", "seller__email", "condition_notes")
    inlines = [ListingImageInline]
