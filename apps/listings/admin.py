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
    def get_readonly_fields(self, request, obj=None):
        if obj and obj.status in (BookListing.Status.RESERVED, BookListing.Status.SOLD):
            return tuple(field.name for field in BookListing._meta.fields)
        return ("condition_needs_review",)
    def has_delete_permission(self, request, obj=None):
        if obj and obj.status in (BookListing.Status.RESERVED, BookListing.Status.SOLD):
            return False
        return super().has_delete_permission(request, obj)


    def get_inline_instances(self, request, obj=None):
        if obj and obj.status in (BookListing.Status.RESERVED, BookListing.Status.SOLD):
            return []
        return super().get_inline_instances(request, obj)
    def save_model(self, request, obj, form, change):
        if obj.condition in BookListing.Condition.values:
            obj.condition_needs_review = False
        super().save_model(request, obj, form, change)
