from rest_framework import generics, permissions, status
from rest_framework.request import Request
from rest_framework.response import Response
from apps.books.models import Book, Category
from apps.books.selectors import search_books
from apps.books.serializers import BookSerializer, CategorySerializer
from apps.books.services.openlibrary import fetch_or_create_book_by_isbn


class BookListView(generics.ListAPIView):
    serializer_class = BookSerializer
    permission_classes = (permissions.AllowAny,)

    def get_queryset(self):
        query = self.request.query_params.get("q", "")
        category = self.request.query_params.get("category", "")
        return search_books(query=query, category_slug=category)


class BookDetailView(generics.RetrieveAPIView):
    serializer_class = BookSerializer
    permission_classes = (permissions.AllowAny,)
    lookup_field = "slug"
    queryset = Book.objects.prefetch_related("authors", "categories")


class CategoryListView(generics.ListAPIView):
    serializer_class = CategorySerializer
    permission_classes = (permissions.AllowAny,)
    queryset = Category.objects.all()


class BookLookupByIsbnView(generics.GenericAPIView):
    """
    Enables sellers to type an ISBN (10 or 13 digits) to auto-fill book title,
    cover, and metadata using OpenLibrary before posting a listing.
    """
    serializer_class = BookSerializer
    permission_classes = (permissions.IsAuthenticated,)

    def post(self, request: Request, *args, **kwargs) -> Response:
        isbn = request.data.get("isbn", "").strip()
        if not isbn:
            return Response({"error": "An ISBN string is required."}, status=status.HTTP_400_BAD_REQUEST)

        book = fetch_or_create_book_by_isbn(isbn)
        if not book:
            return Response(
                {"error": "Book could not be located via local catalog or OpenLibrary."},
                status=status.HTTP_404_NOT_FOUND,
            )

        return Response(BookSerializer(book).data, status=status.HTTP_200_OK)
