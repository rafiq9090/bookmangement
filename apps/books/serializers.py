from rest_framework import serializers
from apps.books.models import Author, Book, Category


class AuthorSerializer(serializers.ModelSerializer):
    class Meta:
        model = Author
        fields = ("id", "name", "slug", "biography", "photo")


class CategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = ("id", "name", "slug", "description")


class BookSerializer(serializers.ModelSerializer):
    authors = AuthorSerializer(many=True, read_only=True)
    categories = CategorySerializer(many=True, read_only=True)
    available_listings_count = serializers.IntegerField(read_only=True, default=0)

    class Meta:
        model = Book
        fields = (
            "id",
            "title",
            "slug",
            "isbn_10",
            "isbn_13",
            "authors",
            "categories",
            "publisher",
            "publication_year",
            "language",
            "cover_image",
            "description",
            "available_listings_count",
        )
