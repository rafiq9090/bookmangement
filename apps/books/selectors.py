from django.conf import settings
from django.db.models import Q, QuerySet
from apps.books.models import Book


def search_books(query: str = "", category_slug: str = "") -> QuerySet[Book]:
    """
    Retrieves canonical books using Trigram similarity and full-text matching on PostgreSQL.
    Safely falls back to case-insensitive icontains if non-PostgreSQL engine is active.
    """
    queryset = Book.objects.prefetch_related("authors", "categories")

    if category_slug:
        queryset = queryset.filter(categories__slug=category_slug)

    clean_query = query.strip()
    if not clean_query:
        return queryset

    # Check if database backend is PostgreSQL
    engine = settings.DATABASES["default"]["ENGINE"]
    if "postgresql" in engine:
        from django.contrib.postgres.search import TrigramSimilarity

        return (
            queryset.annotate(
                title_sim=TrigramSimilarity("title", clean_query),
                isbn_sim=TrigramSimilarity("isbn_13", clean_query),
            )
            .filter(
                Q(title_sim__gt=0.2)
                | Q(isbn_sim__gt=0.3)
                | Q(title__icontains=clean_query)
                | Q(authors__name__icontains=clean_query)
                | Q(isbn_13__icontains=clean_query)
            )
            .order_by("-title_sim", "title")
            .distinct()
        )

    # Standard fallback for SQLite / local testing
    return queryset.filter(
        Q(title__icontains=clean_query)
        | Q(authors__name__icontains=clean_query)
        | Q(isbn_13__icontains=clean_query)
    ).distinct()
