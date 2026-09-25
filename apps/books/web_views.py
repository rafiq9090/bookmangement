from decimal import Decimal
from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Avg, Count, F, Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render

from apps.books.models import Author, Book, BookReview, Category
from apps.listings.models import BookListing
from apps.orders.services.cart import get_cart_items_for_request


def _build_stars_data(avg_rating: float | None) -> dict:
    rating = float(avg_rating or 0)
    full_stars = int(rating)
    has_half = 1 if (rating - full_stars) >= 0.5 else 0
    empty_stars = max(0, 5 - full_stars - has_half)
    return {
        "full": range(full_stars),
        "half": has_half,
        "empty": range(empty_stars),
    }


def home_view(request):
    """
    Renders the Homepage with Hero, Popular Collections, Dynamic Customer Reviews, and Store highlights.
    """
    # Dynamic categories with book counts
    categories = Category.objects.annotate(book_count=Count("books")).order_by("-book_count")[:8]

    # Featured books with dynamic rating annotations
    featured_listings = (
        BookListing.objects.filter(status=BookListing.Status.ACTIVE, is_deleted=False)
        .select_related("book", "seller")
        .prefetch_related("book__authors", "book__categories", "images")
        .annotate(
            avg_rating=Avg("book__reviews__rating"),
            reviews_count=Count("book__reviews", distinct=True),
        )
        .order_by("-created_at")[:8]
    )

    COLLECTION_STYLES = [
        {"bg_gradient": "from-teal-50 to-emerald-100", "book_bg": "bg-[#1E5D57]", "text_color": "text-teal-100", "border": "border-teal-700", "badge": "STAFF PICK", "icon": "fa-book-bookmark", "sub": "Curated Edition"},
        {"bg_gradient": "from-orange-50 to-amber-100", "book_bg": "bg-[#8D3B1B]", "text_color": "text-amber-100", "border": "border-amber-700", "badge": "BESTSELLER", "icon": "fa-award", "sub": "Top Rated"},
        {"bg_gradient": "from-sky-50 to-blue-100", "book_bg": "bg-[#1E3A8A]", "text_color": "text-sky-100", "border": "border-blue-700", "badge": "CLASSIC", "icon": "fa-feather", "sub": "Vintage Copy"},
        {"bg_gradient": "from-purple-50 to-violet-100", "book_bg": "bg-[#4C1D95]", "text_color": "text-violet-100", "border": "border-violet-700", "badge": "RARE FIND", "icon": "fa-gem", "sub": "Collector Choice"},
        {"bg_gradient": "from-rose-50 to-pink-100", "book_bg": "bg-[#831843]", "text_color": "text-rose-100", "border": "border-pink-700", "badge": "FEATURED", "icon": "fa-fire-flame-curved", "sub": "Hot Title"},
        {"bg_gradient": "from-amber-50 to-yellow-100", "book_bg": "bg-[#78350F]", "text_color": "text-amber-100", "border": "border-amber-800", "badge": "MUST READ", "icon": "fa-compass", "sub": "Recommended"},
        {"bg_gradient": "from-emerald-50 to-teal-100", "book_bg": "bg-[#064E3B]", "text_color": "text-emerald-100", "border": "border-emerald-700", "badge": "VERIFIED", "icon": "fa-certificate", "sub": "Quality Inspected"},
        {"bg_gradient": "from-indigo-50 to-slate-100", "book_bg": "bg-[#1E1B4B]", "text_color": "text-indigo-100", "border": "border-indigo-800", "badge": "SPECIAL", "icon": "fa-book-open-reader", "sub": "Handpicked"},
    ]

    featured_books = []
    for idx, listing in enumerate(featured_listings):
        listing.original_price = (listing.price * Decimal("2.00")).quantize(Decimal("0.01"))
        listing.rounded_rating = round(listing.avg_rating or 0, 1)
        listing.stars_data = _build_stars_data(listing.avg_rating)
        featured_books.append({
            "listing": listing,
            "original_price": listing.original_price,
            "style": COLLECTION_STYLES[idx % len(COLLECTION_STYLES)],
        })

    # Authors highlight (exactly 2 rows of 4 on desktop)
    top_authors = Author.objects.annotate(book_count=Count("books")).order_by("-book_count", "name")[:8]
    total_authors_count = Author.objects.count()

    # Dynamic Reviews & Testimonials from database
    recent_reviews = list(
        BookReview.objects.select_related("book", "user")
        .order_by("-created_at")[:6]
    )
    for rev in recent_reviews:
        rev.stars_data = _build_stars_data(rev.rating)
        rev.initials = "".join([part[0].upper() for part in rev.name.split()[:2]]) if rev.name else "R"

    total_reviews_count = BookReview.objects.count()
    overall_rating = (
        round(BookReview.objects.aggregate(avg=Avg("rating"))["avg"] or 5.0, 1)
        if total_reviews_count > 0
        else 5.0
    )

    # Cart count from session or user
    _, _, cart_count = get_cart_items_for_request(request)

    return render(
        request,
        "home.html",
        {
            "categories": categories,
            "featured_listings": featured_listings,
            "featured_books": featured_books,
            "top_authors": top_authors,
            "total_authors_count": total_authors_count,
            "cart_count": cart_count,
            "recent_reviews": recent_reviews,
            "total_reviews_count": total_reviews_count,
            "overall_rating": overall_rating,
        },
    )


def authors_list_view(request):
    """
    Dedicated Authors Directory (/authors/) with search, sorting,
    biographies, book count badges, and direct links to books in store.
    """
    query = request.GET.get("q", "").strip()
    sort = request.GET.get("sort", "books")

    authors = Author.objects.annotate(book_count=Count("books"))

    if query:
        authors = authors.filter(
            Q(name__icontains=query) | Q(biography__icontains=query)
        )

    if sort == "name_asc":
        authors = authors.order_by("name")
    elif sort == "name_desc":
        authors = authors.order_by("-name")
    else:
        authors = authors.order_by("-book_count", "name")

    total_count = authors.count()

    paginator = Paginator(authors, 12)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    # Cart count from session or user
    _, _, cart_count = get_cart_items_for_request(request)

    return render(
        request,
        "books/authors.html",
        {
            "page_obj": page_obj,
            "query": query,
            "sort": sort,
            "total_count": total_count,
            "cart_count": cart_count,
        },
    )


def store_view(request):
    """
    Renders the Store/Catalog browsing page with search, category filtering,
    condition filter, price range, rating filter, sorting, and pagination.
    """
    query = request.GET.get("q", "").strip()
    category_slug = request.GET.get("category", "").strip()
    condition = request.GET.get("condition", "").strip()
    sort = request.GET.get("sort", "newest")
    min_price = request.GET.get("min_price", "").strip()
    max_price = request.GET.get("max_price", "").strip()
    min_rating = request.GET.get("rating", "").strip()

    listings = (
        BookListing.objects.filter(status=BookListing.Status.ACTIVE, is_deleted=False)
        .select_related("book", "seller")
        .prefetch_related("book__authors", "book__categories", "images")
        .annotate(
            avg_rating=Avg("book__reviews__rating"),
            reviews_count=Count("book__reviews", distinct=True),
        )
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

    if min_price:
        try:
            listings = listings.filter(price__gte=Decimal(min_price))
        except (ValueError, ArithmeticError):
            pass

    if max_price:
        try:
            listings = listings.filter(price__lte=Decimal(max_price))
        except (ValueError, ArithmeticError):
            pass

    if min_rating:
        try:
            listings = listings.filter(avg_rating__gte=float(min_rating))
        except (ValueError, TypeError):
            pass

    # Sorting
    if sort == "price_asc":
        listings = listings.order_by("price")
    elif sort == "price_desc":
        listings = listings.order_by("-price")
    elif sort == "rating":
        listings = listings.order_by(F("avg_rating").desc(nulls_last=True), "-reviews_count")
    elif sort == "year":
        listings = listings.order_by(F("book__publication_year").desc(nulls_last=True))
    else:
        listings = listings.order_by("-created_at")

    total_count = listings.count()

    # Annotate original price & stars data
    listings_list = list(listings)
    for l in listings_list:
        l.original_price = (l.price * Decimal("2.00")).quantize(Decimal("0.01"))
        l.rounded_rating = round(l.avg_rating or 0, 1)
        l.stars_data = _build_stars_data(l.avg_rating)

    # Pagination
    paginator = Paginator(listings_list, 12)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    categories = Category.objects.annotate(book_count=Count("books")).order_by("-book_count")
    _, _, cart_count = get_cart_items_for_request(request)

    # Featured community reviews spotlight for store sidebar
    featured_reviews = list(
        BookReview.objects.select_related("book")
        .order_by("-created_at")[:3]
    )
    for rev in featured_reviews:
        rev.stars_data = _build_stars_data(rev.rating)

    return render(
        request,
        "books/store.html",
        {
            "page_obj": page_obj,
            "categories": categories,
            "current_category": category_slug,
            "selected_category": category_slug,
            "current_condition": condition,
            "current_sort": sort,
            "sort": sort,
            "query": query,
            "min_price": min_price,
            "max_price": max_price,
            "min_rating": min_rating,
            "total_count": total_count,
            "conditions": BookListing.Condition.choices,
            "cart_count": cart_count,
            "featured_reviews": featured_reviews,
        },
    )


def book_detail_view(request, slug):
    """
    Renders the Book Detail page with pricing, physical condition grading,
    seller verification, author info, database reviews, and related recommendations.
    """
    book = get_object_or_404(
        Book.objects.prefetch_related(
            "authors",
            "categories",
            "listings__seller",
            "listings__seller__seller_profile",
            "listings__seller__addresses",
            "listings__images",
            "reviews__user",
        ),
        slug=slug,
    )

    is_seller_of_book = request.user.is_authenticated and book.listings.filter(seller=request.user).exists()
    user_has_reviewed = request.user.is_authenticated and book.reviews.filter(user=request.user).exists()

    # Handle Review submission stored directly in database
    if request.method == "POST":
        if is_seller_of_book:
            is_ajax = request.headers.get("x-requested-with") == "XMLHttpRequest"
            if is_ajax:
                return JsonResponse({
                    "success": False,
                    "error": "Sellers cannot review books listed in their own store.",
                }, status=403)
            messages.error(request, "Sellers cannot review books listed in their own store.")
            return redirect(f"/books/{book.slug}/#reviews")

        if user_has_reviewed:
            is_ajax = request.headers.get("x-requested-with") == "XMLHttpRequest"
            if is_ajax:
                return JsonResponse({
                    "success": False,
                    "error": "You have already submitted a review for this book.",
                }, status=400)
            messages.info(request, "You have already submitted a review for this book.")
            return redirect(f"/books/{book.slug}/#reviews")

        name = request.POST.get("name", "").strip()
        headline = request.POST.get("headline", "").strip()
        comment = request.POST.get("comment", "").strip()
        try:
            rating = int(request.POST.get("rating", 5))
            rating = max(1, min(5, rating))
        except (ValueError, TypeError):
            rating = 5

        if not name:
            if request.user.is_authenticated:
                name = request.user.get_full_name() or request.user.email.split("@")[0]
            else:
                name = "Reader"

        user = request.user if request.user.is_authenticated else None
        review = BookReview.objects.create(
            book=book,
            user=user,
            name=name,
            rating=rating,
            headline=headline,
            comment=comment,
        )

        is_ajax = request.headers.get("x-requested-with") == "XMLHttpRequest"
        if is_ajax:
            return JsonResponse({
                "success": True,
                "review": {
                    "id": review.id,
                    "name": review.name,
                    "rating": review.rating,
                    "headline": review.headline,
                    "comment": review.comment,
                    "created_at": "Just now",
                },
            })

        messages.success(request, "Thank you! Your review has been submitted.")
        return redirect(f"/books/{book.slug}/#reviews")

    # Reviews directly from database
    reviews = book.reviews.all().order_by("-created_at")
    reviews_count = reviews.count()
    if reviews_count > 0:
        avg_rating = round(reviews.aggregate(avg=Avg("rating"))["avg"] or 5.0, 1)
        rating_breakdown = {}
        for star in [5, 4, 3, 2, 1]:
            c = sum(1 for r in reviews if r.rating == star)
            pct = int(round((c / reviews_count) * 100))
            rating_breakdown[star] = {"count": c, "percent": pct}
    else:
        avg_rating = 0
        rating_breakdown = {star: {"count": 0, "percent": 0} for star in [5, 4, 3, 2, 1]}

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

    buyer_conversation = None
    confirmed_listing_ids = set()
    is_primary_own_listing = False

    if request.user.is_authenticated:
        from apps.messaging.models import Conversation
        if primary_listing:
            is_primary_own_listing = (primary_listing.seller_id == request.user.id)
            buyer_conversation = Conversation.objects.filter(
                listing=primary_listing,
                buyer=request.user,
            ).first()
        confirmed_listing_ids = set(
            Conversation.objects.filter(
                buyer=request.user,
                listing__book=book,
                order_status=Conversation.OrderStatus.CONFIRMED,
            ).values_list("listing_id", flat=True)
        )

    return render(
        request,
        "books/book_detail.html",
        {
            "book": book,
            "listing": primary_listing,
            "other_listings": active_listings[1:],
            "related_books": related_listings,
            "cart_count": cart_count,
            "reviews": reviews,
            "reviews_count": reviews_count,
            "avg_rating": avg_rating,
            "rating_breakdown": rating_breakdown,
            "is_seller_of_book": is_seller_of_book,
            "is_primary_own_listing": is_primary_own_listing,
            "buyer_conversation": buyer_conversation,
            "confirmed_listing_ids": confirmed_listing_ids,
            "user_has_reviewed": user_has_reviewed,
        },
    )

