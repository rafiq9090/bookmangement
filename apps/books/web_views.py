from decimal import Decimal
from django.core.paginator import Paginator
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, render

from apps.books.models import Author, Book, Category
from apps.listings.models import BookListing
from apps.orders.services.cart import get_cart_items_for_request


def home_view(request):
    """
    Renders the Homepage with Hero, Popular Collections, and Store highlights.
    """
    # Dynamic categories with book counts
    categories = Category.objects.annotate(book_count=Count("books")).order_by("-book_count")[:8]

    # Featured books
    featured_listings = (
        BookListing.objects.filter(status=BookListing.Status.ACTIVE, is_deleted=False)
        .select_related("book", "seller")
        .prefetch_related("book__authors", "book__categories", "images")
        .order_by("-created_at")[:8]
    )

    # Calculate 50% mock original price for demo display
    for listing in featured_listings:
        listing.original_price = (listing.price * Decimal("2.00")).quantize(Decimal("0.01"))

    # Authors highlight
    top_authors = Author.objects.annotate(book_count=Count("books")).order_by("-book_count")[:6]

    # Cart count from session or user
    _, _, cart_count = get_cart_items_for_request(request)

    return render(
        request,
        "home.html",
        {
            "categories": categories,
            "featured_listings": featured_listings,
            "top_authors": top_authors,
            "cart_count": cart_count,
        },
    )


def store_view(request):
    """
    Renders the Store/Catalog browsing page with search, category filtering,
    condition filter, price sorting, and pagination.
    """
    query = request.GET.get("q", "").strip()
    category_slug = request.GET.get("category", "").strip()
    condition = request.GET.get("condition", "").strip()
    sort = request.GET.get("sort", "newest")

    listings = (
        BookListing.objects.filter(status=BookListing.Status.ACTIVE, is_deleted=False)
        .select_related("book", "seller")
        .prefetch_related("book__authors", "book__categories", "images")
    )

    if query:
        listings = listings.filter(
            Q(book__title__icontains=query)
            | Q(book__authors__name__icontains=query)
            | Q(book__isbn_10__icontains=query)
            | Q(book__isbn_13__icontains=query)
        ).distinct()

    if category_slug:
        listings = listings.filter(book__categories__slug=category_slug)

    if condition:
        listings = listings.filter(condition=condition)

    # Sorting
    if sort == "price_asc":
        listings = listings.order_by("price")
    elif sort == "price_desc":
        listings = listings.order_by("-price")
    else:
        listings = listings.order_by("-created_at")

    # Annotate original price
    listings_list = list(listings)
    for l in listings_list:
        l.original_price = (l.price * Decimal("2.00")).quantize(Decimal("0.01"))

    # Pagination
    paginator = Paginator(listings_list, 12)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    categories = Category.objects.annotate(book_count=Count("books")).order_by("-book_count")
    _, _, cart_count = get_cart_items_for_request(request)

    return render(
        request,
        "books/store.html",
        {
            "page_obj": page_obj,
            "categories": categories,
            "current_category": category_slug,
            "current_condition": condition,
            "current_sort": sort,
            "query": query,
            "conditions": BookListing.Condition.choices,
            "cart_count": cart_count,
        },
    )


def book_detail_view(request, slug):
    """
    Renders the Book Detail page with pricing, physical condition grading,
    seller verification, author info, and related recommendations.
    """
    book = get_object_or_404(
        Book.objects.prefetch_related("authors", "categories", "listings__seller", "listings__images"),
        slug=slug,
    )

    # Primary listing for purchase
    active_listings = book.listings.filter(status=BookListing.Status.ACTIVE, is_deleted=False).order_by("price")
    primary_listing = active_listings.first()

    if primary_listing:
        primary_listing.original_price = (primary_listing.price * Decimal("2.00")).quantize(Decimal("0.01"))

    # Related books from the same category
    first_category = book.categories.first()
    related_listings = []
    if first_category:
        related_listings = (
            BookListing.objects.filter(
                book__categories=first_category,
                status=BookListing.Status.ACTIVE,
                is_deleted=False,
            )
            .exclude(book=book)
            .select_related("book", "seller")
            .prefetch_related("book__authors", "images")[:4]
        )
        for rel in related_listings:
            rel.original_price = (rel.price * Decimal("2.00")).quantize(Decimal("0.01"))

    _, _, cart_count = get_cart_items_for_request(request)

    return render(
        request,
        "books/book_detail.html",
        {
            "book": book,
            "listing": primary_listing,
            "other_listings": active_listings[1:],
            "related_books": related_listings,
            "cart_count": cart_count,
        },
    )
