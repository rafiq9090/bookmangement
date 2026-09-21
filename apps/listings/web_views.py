from decimal import Decimal
import uuid
from django.db import transaction
from django.db.models import Q, Sum
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.text import slugify

from apps.accounts.models import CustomUser
from apps.books.models import Author, Book, Category
from apps.listings.models import BookListing, ListingImage
from apps.orders.services.cart import get_cart_items_for_request
from apps.payments.models import SellerLedger


def get_or_create_seller_user(request):
    """
    Returns the authenticated user or falls back to an existing seller user in development.
    """
    if request.user.is_authenticated:
        return request.user
    seller = CustomUser.objects.filter(is_seller=True).first()
    if not seller:
        seller = CustomUser.objects.first()
    if not seller:
        seller = CustomUser.objects.create_user(
            email="seller@edoxbookshop.com",
            password="DemoPassword123!",
            first_name="Ronald",
            last_name="Richards",
            is_seller=True,
        )
    return seller


def sell_book_view(request):
    """
    Page 6: Sell Book / Create Listing (/sell/)
    Supports ISBN autofill, physical condition grading, defect notes,
    feature checkboxes, price, and cover image upload.
    """
    seller = get_or_create_seller_user(request)
    categories = Category.objects.all().order_by("name")
    _, _, cart_count = get_cart_items_for_request(request)

    if request.method == "POST":
        isbn = request.POST.get("isbn", "").strip().replace("-", "")
        title = request.POST.get("title", "").strip()
        author_name = request.POST.get("author", "Independent Author").strip()
        category_id = request.POST.get("category_id")
        price = Decimal(request.POST.get("price", "12.00").strip() or "12.00")
        original_mrp_str = request.POST.get("original_mrp", "").strip()
        original_mrp = Decimal(original_mrp_str) if original_mrp_str else (price * Decimal("1.80")).quantize(Decimal("0.01"))
        condition = request.POST.get("condition", BookListing.Condition.GOOD)
        condition_notes = request.POST.get("condition_notes", "").strip()
        edition_year_str = request.POST.get("edition_year", "").strip()
        edition_year = int(edition_year_str) if edition_year_str.isdigit() else None
        is_hardcover = bool(request.POST.get("is_hardcover"))
        has_dust_jacket = bool(request.POST.get("has_dust_jacket"))
        is_signed_by_author = bool(request.POST.get("is_signed_by_author"))

        with transaction.atomic():
            author, _ = Author.objects.get_or_create(
                name=author_name,
                defaults={"slug": slugify(author_name) or "author-unknown"},
            )

            if category_id:
                category = Category.objects.filter(id=category_id).first()
            else:
                category = Category.objects.first()

            if not isbn:
                isbn = f"978{uuid.uuid4().hex[:10].upper()}"

            book, created = Book.objects.get_or_create(
                isbn_13=isbn[:13] if len(isbn) >= 13 else f"978{isbn[:10]}",
                defaults={
                    "title": title or "Untitled Book",
                    "slug": slugify(title or "untitled-book") + f"-{uuid.uuid4().hex[:6]}",
                    "isbn_10": isbn[:10],
                    "publication_year": edition_year or 2021,
                },
            )
            if created:
                book.authors.add(author)
                if category:
                    book.categories.add(category)

            listing = BookListing.objects.create(
                book=book,
                seller=seller,
                condition=condition,
                condition_notes=condition_notes,
                price=price,
                original_mrp=original_mrp,
                edition_year=edition_year,
                is_hardcover=is_hardcover,
                has_dust_jacket=has_dust_jacket,
                is_signed_by_author=is_signed_by_author,
                status=BookListing.Status.ACTIVE,
            )

            photos = request.FILES.getlist("photos")
            for i, photo in enumerate(photos[:4]):
                ListingImage.objects.create(
                    listing=listing,
                    image=photo,
                    is_primary=(i == 0),
                )

        return redirect("seller_listings")

    return render(
        request,
        "listings/listing_create.html",
        {
            "categories": categories,
            "conditions": BookListing.Condition.choices,
            "cart_count": cart_count,
        },
    )


def isbn_lookup_api(request):
    """
    AJAX helper for ISBN lookup to autofill title, author, and category.
    """
    isbn = request.GET.get("isbn", "").strip().replace("-", "")
    if not isbn:
        return JsonResponse({"found": False})

    book = Book.objects.filter(Q(isbn_10=isbn) | Q(isbn_13=isbn)).prefetch_related("authors", "categories").first()
    if book:
        return JsonResponse(
            {
                "found": True,
                "title": book.title,
                "author": book.authors.first().name if book.authors.exists() else "",
                "category_id": book.categories.first().id if book.categories.exists() else None,
                "publication_year": book.publication_year,
            }
        )
    return JsonResponse({"found": False})


def seller_listings_view(request):
    """
    Page 7: Seller Dashboard / My Listings (/seller/listings/)
    Displays active, reserved, sold, and draft listings with inventory metrics.
    """
    seller = get_or_create_seller_user(request)
    status_filter = request.GET.get("status", "ALL").upper()
    query = request.GET.get("q", "").strip()

    all_seller_listings = BookListing.objects.filter(seller=seller, is_deleted=False).select_related("book").prefetch_related("images", "book__authors")
    
    total_listings = all_seller_listings.count()
    active_count = all_seller_listings.filter(status=BookListing.Status.ACTIVE).count()
    sold_count = all_seller_listings.filter(status=BookListing.Status.SOLD).count()
    
    revenue_agg = SellerLedger.objects.filter(seller=seller, entry_type=SellerLedger.EntryType.SALE_CREDIT).aggregate(total=Sum("amount"))
    total_revenue = revenue_agg["total"] or Decimal("0.00")

    listings = all_seller_listings
    if status_filter != "ALL":
        listings = listings.filter(status=status_filter)
    if query:
        listings = listings.filter(Q(book__title__icontains=query) | Q(book__isbn_13__icontains=query))

    _, _, cart_count = get_cart_items_for_request(request)

    return render(
        request,
        "listings/my_listings.html",
        {
            "listings": listings,
            "current_status": status_filter,
            "query": query,
            "total_listings": total_listings,
            "active_count": active_count,
            "sold_count": sold_count,
            "total_revenue": total_revenue,
            "cart_count": cart_count,
        },
    )


def toggle_listing_view(request, id):
    """
    Toggles a listing between ACTIVE and ARCHIVED.
    """
    seller = get_or_create_seller_user(request)
    listing = get_object_or_404(BookListing, id=id, seller=seller)
    if listing.status == BookListing.Status.ACTIVE:
        listing.status = BookListing.Status.ARCHIVED
    else:
        listing.status = BookListing.Status.ACTIVE
    listing.save(update_fields=["status", "updated_at"])
    return redirect("seller_listings")
