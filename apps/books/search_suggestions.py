from django.db.models import Q, Exists, OuterRef
from django.http import JsonResponse
from django.views.decorators.http import require_GET
from apps.listings.models import BookListing
from .models import Book, Author


@require_GET
def search_suggestions(request):
    query = request.GET.get('q', '').strip()[:100]
    if len(query) < 2:
        return JsonResponse({'suggestions': []})
    available = BookListing.objects.filter(book_id=OuterRef('pk'), status='ACTIVE', is_deleted=False, condition_needs_review=False)
    books = Book.objects.annotate(available=Exists(available)).filter(available=True).filter(
        Q(title__icontains=query) | Q(authors__name__icontains=query) | Q(isbn_10__icontains=query) | Q(isbn_13__icontains=query)
    ).distinct().prefetch_related('authors').order_by('title')[:6]
    suggestions = [{'label': book.title, 'value': book.title, 'detail': ', '.join(a.name for a in book.authors.all()), 'kind': 'Book'} for book in books]
    authors = Author.objects.filter(name__icontains=query, books__listings__status='ACTIVE', books__listings__is_deleted=False, books__listings__condition_needs_review=False).distinct().order_by('name')[:2]
    suggestions.extend({'label': author.name, 'value': author.name, 'detail': 'Browse available books by this author', 'kind': 'Author'} for author in authors)
    return JsonResponse({'suggestions': suggestions})
