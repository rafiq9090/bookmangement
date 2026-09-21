from django.contrib import admin
from apps.books.models import Author, Book, BookReview, Category


@admin.register(Author)
class AuthorAdmin(admin.ModelAdmin):
    list_display = ("name", "slug")
    search_fields = ("name",)
    prepopulated_fields = {"slug": ("name",)}


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "parent")
    search_fields = ("name",)
    prepopulated_fields = {"slug": ("name",)}


@admin.register(Book)
class BookAdmin(admin.ModelAdmin):
    list_display = ("title", "isbn_13", "publisher", "publication_year", "created_at")
    search_fields = ("title", "isbn_13", "isbn_10", "authors__name")
    list_filter = ("publication_year", "language")
    filter_horizontal = ("authors", "categories")


@admin.register(BookReview)
class BookReviewAdmin(admin.ModelAdmin):
    list_display = ("book", "name", "rating", "headline", "created_at")
    list_filter = ("rating", "created_at")
    search_fields = ("book__title", "name", "headline", "comment")
