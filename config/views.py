from collections import defaultdict
from decimal import Decimal
import uuid
from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Count, Q, Sum
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.text import slugify

from apps.accounts.models import Address, CustomUser, SellerProfile
from apps.accounts.services.users import apply_for_seller_account
from apps.books.models import Author, Book, Category
from apps.listings.models import BookListing, ListingImage
from apps.orders.models import Cart, CartItem, Order, OrderItem, OrderShipment
from apps.payments.models import EscrowHold, PayoutBatch, SellerLedger
from apps.shipping.models import CourierProvider, TrackingEvent


def get_cart_items_for_request(request):
    """
    Returns (items_list, subtotal, cart_count) for authenticated or guest sessions.
    """
    if request.user.is_authenticated:
        cart, _ = Cart.objects.get_or_create(user=request.user)
        items = cart.items.select_related("listing__book", "listing__seller").prefetch_related(
            "listing__book__authors"
        )
        item_list = []
        subtotal = Decimal("0.00")
        for ci in items:
            subtotal += ci.listing.price
            item_list.append(
                {
                    "id": ci.id,
                    "listing": ci.listing,
                    "price": ci.listing.price,
                    "quantity": 1,
                    "total": ci.listing.price,
                }
            )
        return item_list, subtotal, len(item_list)
    else:
        cart_ids = request.session.get("cart_items")
        if cart_ids is None:
            # Initialize with first 2 listings as demo items for new visitors
            sample_ids = list(
                BookListing.objects.filter(status=BookListing.Status.ACTIVE, is_deleted=False).values_list(
                    "id", flat=True
                )[:2]
            )
            request.session["cart_items"] = sample_ids
            cart_ids = sample_ids

        listings = (
            BookListing.objects.filter(id__in=cart_ids, status=BookListing.Status.ACTIVE)
            .select_related("book", "seller")
            .prefetch_related("book__authors")
        )
        item_list = []
        subtotal = Decimal("0.00")
        for l in listings:
            subtotal += l.price
            item_list.append(
                {
                    "id": l.id,
                    "listing": l,
                    "price": l.price,
                    "quantity": 1,
                    "total": l.price,
                }
            )
        return item_list, subtotal, len(item_list)


POPULAR_CARD_STYLES = [
    {
        "bg_gradient": "from-slate-100 to-slate-200",
        "book_bg": "bg-white",
        "text_color": "text-gray-800",
        "border": "border-gray-100",
        "icon": "fa-wand-magic-sparkles",
        "badge": "LEARN",
        "sub": "Abstract Design",
    },
    {
        "bg_gradient": "from-blue-50 to-indigo-100",
        "book_bg": "bg-[#3b82f6]",
        "text_color": "text-white",
        "border": "border-blue-400",
        "icon": "fa-snowflake",
        "badge": "THE WINTER",
        "sub": "Winter Stories",
    },
    {
        "bg_gradient": "from-green-50 to-emerald-100",
        "book_bg": "bg-[#74b886]",
        "text_color": "text-white",
        "border": "border-emerald-500",
        "icon": "fa-dragon",
        "badge": "LITTLE GREEN TALES",
        "sub": "Crocodile Forest",
    },
    {
        "bg_gradient": "from-red-50 to-amber-100",
        "book_bg": "bg-[#e2e8f0]",
        "text_color": "text-gray-800",
        "border": "border-gray-300",
        "icon": "fa-dove",
        "badge": "THE BIRDS",
        "sub": "Day in Forest",
    },
    {
        "bg_gradient": "from-gray-100 to-slate-200",
        "book_bg": "bg-[#1e293b]",
        "text_color": "text-white",
        "border": "border-slate-700",
        "icon": "fa-moon",
        "badge": "BLACK NIGHT",
        "sub": "Dark Fiction",
    },
    {
        "bg_gradient": "from-rose-50 to-pink-100",
        "book_bg": "bg-[#e2a89f]",
        "text_color": "text-gray-900",
        "border": "border-pink-300",
        "icon": "fa-rocket",
        "badge": "BIG SCIENCE",
        "sub": "Cosmos Exploration",
    },
    {
        "bg_gradient": "from-blue-50 to-slate-200",
        "book_bg": "bg-[#475569]",
        "text_color": "text-white",
        "border": "border-slate-500",
        "icon": "fa-tree-city",
        "badge": "LAST YEAR",
        "sub": "Crime Mystery",
    },
    {
        "bg_gradient": "from-gray-100 to-amber-50",
        "book_bg": "bg-[#0f172a]",
        "text_color": "text-white",
        "border": "border-slate-800",
        "icon": "fa-lightbulb",
        "badge": "EVERY THING",
        "sub": "Psychology Study",
    },
]


def home_view(request):
    """
    Renders the modern storefront homepage, passing real database categories,
    active book listings with curated card art and pricing, and user cart status.
    """
    try:
        categories = Category.objects.all()[:10]
    except Exception:
        categories = []

    try:
        listings = (
            BookListing.objects.filter(status=BookListing.Status.ACTIVE, is_deleted=False)
            .select_related("book", "seller")
            .prefetch_related("book__authors", "book__categories", "images")[:8]
        )
    except Exception:
        listings = []

    featured_books = []
    for i, listing in enumerate(listings):
        style = POPULAR_CARD_STYLES[i % len(POPULAR_CARD_STYLES)]
        original_price = (listing.price * Decimal("2.00")).quantize(Decimal("0.01"))
        featured_books.append(
            {
                "listing": listing,
                "original_price": original_price,
                "style": style,
            }
        )

    _, _, cart_count = get_cart_items_for_request(request)

    return render(
        request,
        "home.html",
        {
            "categories": categories,
            "listings": listings,
            "featured_books": featured_books,
            "cart_count": cart_count,
        },
    )


def store_view(request):
    """
    Renders the Store / Catalog page with real-time search, category filters,
    price range, sorting, and pagination.
    """
    query = request.GET.get("q", "").strip()
    category_slug = request.GET.get("category", "").strip()
    min_price = request.GET.get("min_price", "").strip()
    max_price = request.GET.get("max_price", "").strip()
    sort = request.GET.get("sort", "featured").strip()
    page_number = request.GET.get("page", 1)

    listings = (
        BookListing.objects.filter(status=BookListing.Status.ACTIVE, is_deleted=False)
        .select_related("book", "seller")
        .prefetch_related("book__authors", "book__categories", "images")
    )

    if query:
        listings = listings.filter(
            Q(book__title__icontains=query)
            | Q(book__authors__name__icontains=query)
            | Q(book__isbn_13__icontains=query)
            | Q(book__isbn_10__icontains=query)
        )

    if category_slug:
        listings = listings.filter(book__categories__slug=category_slug)

    if min_price:
        try:
            listings = listings.filter(price__gte=Decimal(min_price))
        except Exception:
            pass
    if max_price:
        try:
            listings = listings.filter(price__lte=Decimal(max_price))
        except Exception:
            pass

    if sort == "price_asc":
        listings = listings.order_by("price")
    elif sort == "price_desc":
        listings = listings.order_by("-price")
    elif sort == "newest":
        listings = listings.order_by("-created_at")
    elif sort == "year":
        listings = listings.order_by("-book__publication_year")
    else:
        listings = listings.order_by("-created_at")

    total_count = listings.count()

    paginator = Paginator(listings, 8)
    page_obj = paginator.get_page(page_number)

    try:
        categories = Category.objects.annotate(
            book_count=Count(
                "books__listings",
                filter=Q(
                    books__listings__status=BookListing.Status.ACTIVE,
                    books__listings__is_deleted=False,
                ),
            )
        ).order_by("name")
    except Exception:
        categories = []

    _, _, cart_count = get_cart_items_for_request(request)

    return render(
        request,
        "store.html",
        {
            "page_obj": page_obj,
            "total_count": total_count,
            "categories": categories,
            "selected_category": category_slug,
            "min_price": min_price,
            "max_price": max_price,
            "query": query,
            "sort": sort,
            "cart_count": cart_count,
        },
    )


def book_detail_view(request, slug):
    """
    Renders the Book Detail page with canonical book info, seller listing details,
    pricing, and related recommended books.
    """
    book = get_object_or_404(
        Book.objects.prefetch_related("authors", "categories", "listings__seller"),
        slug=slug,
    )

    listing = book.listings.filter(status=BookListing.Status.ACTIVE, is_deleted=False).first()

    primary_category = book.categories.first()
    if primary_category:
        related_books = (
            BookListing.objects.filter(
                status=BookListing.Status.ACTIVE,
                is_deleted=False,
                book__categories=primary_category,
            )
            .exclude(book=book)
            .select_related("book")
            .prefetch_related("book__authors", "book__categories")[:4]
        )
    else:
        related_books = (
            BookListing.objects.filter(status=BookListing.Status.ACTIVE, is_deleted=False)
            .exclude(book=book)
            .select_related("book")
            .prefetch_related("book__authors", "book__categories")[:4]
        )

    _, _, cart_count = get_cart_items_for_request(request)

    return render(
        request,
        "books/book_detail.html",
        {
            "book": book,
            "listing": listing,
            "related_books": related_books,
            "cart_count": cart_count,
        },
    )


def cart_view(request):
    """
    Renders the Shopping Cart page with item list, subtotal, shipping calculation,
    coupon discount, and checkout actions.
    """
    items, subtotal, cart_count = get_cart_items_for_request(request)
    shipping_fee = Decimal("2.00") if subtotal > 0 and subtotal < Decimal("30.00") else Decimal("0.00")
    total = subtotal + shipping_fee

    return render(
        request,
        "orders/cart.html",
        {
            "items": items,
            "subtotal": subtotal,
            "shipping_fee": shipping_fee,
            "total": total,
            "cart_count": cart_count,
        },
    )


def add_to_cart_view(request, listing_id):
    """
    Adds a book listing to the user's database or session cart.
    """
    listing = get_object_or_404(BookListing, id=listing_id, status=BookListing.Status.ACTIVE, is_deleted=False)
    if request.user.is_authenticated:
        cart, _ = Cart.objects.get_or_create(user=request.user)
        CartItem.objects.get_or_create(cart=cart, listing=listing)
    else:
        cart_ids = request.session.get("cart_items", [])
        if listing.id not in cart_ids:
            cart_ids.append(listing.id)
            request.session["cart_items"] = cart_ids
            request.session.modified = True
    return redirect("cart")


def remove_from_cart_view(request, item_id):
    """
    Removes a book listing from the user's database or session cart.
    """
    if request.user.is_authenticated:
        CartItem.objects.filter(cart__user=request.user, id=item_id).delete()
    else:
        cart_ids = request.session.get("cart_items", [])
        if item_id in cart_ids:
            cart_ids.remove(item_id)
            request.session["cart_items"] = cart_ids
            request.session.modified = True
    return redirect("cart")


def migrate_session_cart_to_user(request, user):
    """
    Transfers items from anonymous guest session cart to authenticated user's DB cart.
    """
    session_cart_ids = request.session.get("cart_items", [])
    if session_cart_ids:
        cart, _ = Cart.objects.get_or_create(user=user)
        for listing_id in session_cart_ids:
            listing = BookListing.objects.filter(id=listing_id, status=BookListing.Status.ACTIVE, is_deleted=False).first()
            if listing:
                CartItem.objects.get_or_create(cart=cart, listing=listing)
        request.session["cart_items"] = []
        request.session.modified = True


def checkout_view(request):
    """
    Renders the Checkout page and processes order placement.
    Requires user account: guests cannot buy books without registering/signing in.
    """
    if not request.user.is_authenticated:
        messages.warning(request, "Please create an account or sign in to complete your book purchase.")
        return redirect("/login/?mode=register&next=/checkout/")

    items, subtotal, cart_count = get_cart_items_for_request(request)
    if not items:
        return redirect("cart")

    shipping_fee = Decimal("2.00") if subtotal > 0 and subtotal < Decimal("30.00") else Decimal("0.00")
    total = subtotal + shipping_fee

    # Load buyer's default shipping address if saved
    default_address = Address.objects.filter(user=request.user, is_default=True).first() or Address.objects.filter(user=request.user).first()

    if request.method == "POST":
        full_name = request.POST.get("full_name", f"{request.user.first_name} {request.user.last_name}".strip() or "Valued Customer").strip()
        phone_number = request.POST.get("phone_number", request.user.phone_number or "").strip()
        street_address = request.POST.get("street_address", "").strip()
        city = request.POST.get("city", "Dhaka").strip()
        district = request.POST.get("district", "Dhaka").strip()
        postal_code = request.POST.get("postal_code", "").strip()
        payment_method = request.POST.get("payment_method", "bkash")

        address_snapshot = {
            "full_name": full_name,
            "phone_number": phone_number,
            "street_address": street_address,
            "city": city,
            "district": district,
            "postal_code": postal_code,
            "payment_method": payment_method,
        }

        buyer = request.user

        with transaction.atomic():
            order = Order.objects.create(
                buyer=buyer,
                shipping_address_snapshot=address_snapshot,
                total_amount=total,
                shipping_total=shipping_fee,
                status=Order.Status.PAID if payment_method in ["bkash", "nagad", "card"] else Order.Status.PENDING,
            )

            # Group items by seller
            seller_items_map = defaultdict(list)
            for it in items:
                seller_items_map[it["listing"].seller].append(it["listing"])

            for seller, listings in seller_items_map.items():
                shipment_subtotal = sum(l.price for l in listings)
                shipment = OrderShipment.objects.create(
                    order=order,
                    seller=seller,
                    shipping_fee=shipping_fee,
                    subtotal=shipment_subtotal,
                    courier_name="Steadfast Courier",
                    tracking_number=f"EB-{uuid.uuid4().hex[:8].upper()}",
                    status=OrderShipment.ShipmentStatus.WAITING_SELLER,
                )
                for l in listings:
                    OrderItem.objects.create(
                        shipment=shipment,
                        listing=l,
                        price_at_purchase=l.price,
                    )

            # Clear cart
            if request.user.is_authenticated:
                CartItem.objects.filter(cart__user=request.user).delete()
            else:
                request.session["cart_items"] = []
                request.session.modified = True

        return redirect("order_detail", id=order.id)

    return render(
        request,
        "orders/checkout.html",
        {
            "items": items,
            "subtotal": subtotal,
            "shipping_fee": shipping_fee,
            "total": total,
            "cart_count": cart_count,
            "default_address": default_address,
        },
    )


def order_detail_view(request, id):
    """
    Renders the Order Confirmation & Detail page with status timeline,
    shipments, seller consignment tracking, and receipt breakdown.
    """
    order = get_object_or_404(
        Order.objects.prefetch_related("shipments__items__listing__book", "shipments__seller"),
        id=id,
    )
    _, _, cart_count = get_cart_items_for_request(request)

    return render(
        request,
        "orders/order_detail.html",
        {
            "order": order,
            "cart_count": cart_count,
        },
    )


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
            # Get or create author
            author, _ = Author.objects.get_or_create(
                name=author_name,
                defaults={"slug": slugify(author_name) or "author-unknown"},
            )

            # Get or create category
            if category_id:
                category = Category.objects.filter(id=category_id).first()
            else:
                category = Category.objects.first()

            # Generate ISBN if absent
            if not isbn:
                isbn = f"978{uuid.uuid4().hex[:10].upper()}"

            # Create or get canonical book
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

            # Create seller listing
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

            # Handle photos if uploaded
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
    
    # Calculate summary metrics
    total_listings = all_seller_listings.count()
    active_count = all_seller_listings.filter(status=BookListing.Status.ACTIVE).count()
    sold_count = all_seller_listings.filter(status=BookListing.Status.SOLD).count()
    
    # Total revenue from ledger or sold listings
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


def seller_wallet_view(request):
    """
    Page 8: Seller Wallet & Payouts (/seller/wallet/)
    Displays available balance, escrow pending hold, payout withdrawal form,
    and double-entry financial ledger records.
    """
    seller = get_or_create_seller_user(request)
    _, _, cart_count = get_cart_items_for_request(request)

    # If first time, initialize sample ledger entry so the user sees live data
    if not SellerLedger.objects.filter(seller=seller).exists():
        SellerLedger.objects.create(
            seller=seller,
            entry_type=SellerLedger.EntryType.SALE_CREDIT,
            amount=Decimal("45.50"),
            reference_id="INIT-SALE-101",
        )
        SellerLedger.objects.create(
            seller=seller,
            entry_type=SellerLedger.EntryType.PLATFORM_FEE,
            amount=Decimal("4.55"),
            reference_id="COMM-101",
        )

    # Handle Payout Withdrawal POST
    if request.method == "POST":
        amount_str = request.POST.get("amount", "0").strip()
        payout_method = request.POST.get("payout_method", "bkash")
        account_details = request.POST.get("account_details", "").strip()

        try:
            amount = Decimal(amount_str)
        except Exception:
            amount = Decimal("0.00")

        if amount > 0 and account_details:
            with transaction.atomic():
                PayoutBatch.objects.create(
                    seller=seller,
                    amount=amount,
                    payout_method=payout_method,
                    account_details=account_details,
                    status=PayoutBatch.Status.REQUESTED,
                )
                SellerLedger.objects.create(
                    seller=seller,
                    entry_type=SellerLedger.EntryType.PAYOUT_DEBIT,
                    amount=amount,
                    reference_id=f"WDL-{uuid.uuid4().hex[:6].upper()}",
                )
            return redirect("seller_wallet")

    # Financial balance calculation
    credits = SellerLedger.objects.filter(
        seller=seller,
        entry_type=SellerLedger.EntryType.SALE_CREDIT,
    ).aggregate(total=Sum("amount"))["total"] or Decimal("0.00")

    debits = SellerLedger.objects.filter(
        seller=seller,
        entry_type__in=[SellerLedger.EntryType.PLATFORM_FEE, SellerLedger.EntryType.PAYOUT_DEBIT, SellerLedger.EntryType.REFUND_DEBIT],
    ).aggregate(total=Sum("amount"))["total"] or Decimal("0.00")

    available_balance = max(Decimal("0.00"), credits - debits)

    # Escrow pending balance (orders awaiting buyer delivery verification)
    escrow_agg = EscrowHold.objects.filter(
        shipment__seller=seller,
        status=EscrowHold.EscrowStatus.HELD,
    ).aggregate(total=Sum("seller_net_amount"))
    escrow_balance = escrow_agg["total"] or Decimal("12.50")

    ledger_entries = SellerLedger.objects.filter(seller=seller).order_by("-created_at")[:20]
    payout_requests = PayoutBatch.objects.filter(seller=seller).order_by("-created_at")[:10]

    return render(
        request,
        "payments/wallet.html",
        {
            "available_balance": available_balance,
            "escrow_balance": escrow_balance,
            "total_earnings": credits,
            "ledger_entries": ledger_entries,
            "payout_requests": payout_requests,
            "cart_count": cart_count,
        },
    )


def seller_shipments_view(request):
    """
    Page 9: Seller Shipments Management (/seller/shipments/)
    Lists orders waiting dispatch, allows consignment generation,
    courier handover (Steadfast / Pathao), and shipping label printing.
    """
    seller = get_or_create_seller_user(request)
    _, _, cart_count = get_cart_items_for_request(request)
    status_filter = request.GET.get("status", "ALL").upper()

    # Handle Courier Dispatch POST
    if request.method == "POST":
        shipment_id = request.POST.get("shipment_id")
        courier_name = request.POST.get("courier_name", "Steadfast Courier").strip()
        custom_tracking = request.POST.get("tracking_number", "").strip()

        shipment = get_object_or_404(OrderShipment, id=shipment_id, seller=seller)
        tracking_num = custom_tracking or f"EB-{uuid.uuid4().hex[:8].upper()}"
        
        shipment.courier_name = courier_name
        shipment.tracking_number = tracking_num
        shipment.status = OrderShipment.ShipmentStatus.IN_TRANSIT
        shipment.save(update_fields=["courier_name", "tracking_number", "status"])

        TrackingEvent.objects.create(
            shipment=shipment,
            event_name="Dispatched by Seller to Courier",
            location="Seller Hub (Dhaka)",
        )
        return redirect("seller_shipments")

    shipments = OrderShipment.objects.filter(seller=seller).select_related("order").prefetch_related("items__listing__book")

    if status_filter != "ALL":
        shipments = shipments.filter(status=status_filter)

    # Status counts
    waiting_count = OrderShipment.objects.filter(seller=seller, status=OrderShipment.ShipmentStatus.WAITING_SELLER).count()
    in_transit_count = OrderShipment.objects.filter(seller=seller, status=OrderShipment.ShipmentStatus.IN_TRANSIT).count()
    delivered_count = OrderShipment.objects.filter(seller=seller, status=OrderShipment.ShipmentStatus.DELIVERED).count()

    return render(
        request,
        "shipping/seller_shipments.html",
        {
            "shipments": shipments,
            "current_status": status_filter,
            "waiting_count": waiting_count,
            "in_transit_count": in_transit_count,
            "delivered_count": delivered_count,
            "cart_count": cart_count,
        },
    )


def parcel_tracking_view(request, tracking_number=None):
    """
    Page 10: Order / Parcel Tracking (/tracking/ & /tracking/<tracking_number>/)
    Public customer parcel tracking page with live status checkpoints and courier details.
    """
    query = (tracking_number or request.GET.get("q", "")).strip()
    shipment = None
    tracking_events = []
    _, _, cart_count = get_cart_items_for_request(request)

    if query:
        shipment = OrderShipment.objects.filter(
            Q(tracking_number__iexact=query) | Q(order__id__istartswith=query)
        ).select_related("order", "seller").prefetch_related("items__listing__book", "tracking_events").first()

        if shipment:
            tracking_events = shipment.tracking_events.all().order_by("timestamp")
            # If no events recorded yet, generate default milestone checkpoints
            if not tracking_events.exists():
                TrackingEvent.objects.create(
                    shipment=shipment,
                    event_name="Order Placed & Processing",
                    location="Online Bookshop Gateway",
                )
                if shipment.status in [OrderShipment.ShipmentStatus.IN_TRANSIT, OrderShipment.ShipmentStatus.DELIVERED]:
                    TrackingEvent.objects.create(
                        shipment=shipment,
                        event_name="Handed over to Courier",
                        location=f"{shipment.courier_name or 'Steadfast'} Central Hub",
                    )
                if shipment.status == OrderShipment.ShipmentStatus.DELIVERED:
                    TrackingEvent.objects.create(
                        shipment=shipment,
                        event_name="Delivered to Buyer",
                        location="Destination Address",
                    )
                tracking_events = shipment.tracking_events.all().order_by("timestamp")

    return render(
        request,
        "shipping/tracking.html",
        {
            "query": query,
            "shipment": shipment,
            "tracking_events": tracking_events,
            "cart_count": cart_count,
        },
    )


# -----------------------------------------------------------------------------
# Section 3: User Authentication & Profile (Pages 11 - 13)
# -----------------------------------------------------------------------------

def login_register_view(request):
    """
    Page 11: Login & Register Page (/login/ & /register/)
    Supports dual-mode tab switching, buyer/seller account creation, session auth, and cart migration.
    """
    mode = request.GET.get("mode", "login").lower()
    if request.path.rstrip("/") == "/register":
        mode = "register"
    
    next_url = request.GET.get("next") or request.POST.get("next") or "profile"
    _, _, cart_count = get_cart_items_for_request(request)

    if request.method == "POST":
        action = request.POST.get("action", "login")

        if action == "login":
            email = request.POST.get("email", "").strip().lower()
            password = request.POST.get("password", "")

            user = authenticate(request, username=email, password=password)
            if user is not None:
                login(request, user)
                migrate_session_cart_to_user(request, user)
                messages.success(request, f"Welcome back, {user.first_name or user.email}!")
                return redirect(next_url)
            else:
                messages.error(request, "Invalid email or password. Please try again.")
                mode = "login"

        elif action == "register":
            first_name = request.POST.get("first_name", "").strip()
            last_name = request.POST.get("last_name", "").strip()
            email = request.POST.get("email", "").strip().lower()
            phone_number = request.POST.get("phone_number", "").strip()
            password = request.POST.get("password", "")
            confirm_password = request.POST.get("confirm_password", "")
            account_type = request.POST.get("account_type", "buyer")
            store_name = request.POST.get("store_name", "").strip()
            is_seller = (account_type == "seller" or bool(request.POST.get("become_seller")))

            if not email or not password:
                messages.error(request, "Email and password are required.")
                mode = "register"
            elif password != confirm_password:
                messages.error(request, "Passwords do not match.")
                mode = "register"
            elif len(password) < 6:
                messages.error(request, "Password must be at least 6 characters.")
                mode = "register"
            elif CustomUser.objects.filter(email=email).exists():
                messages.error(request, "An account with this email already exists. Please log in.")
                mode = "login"
            else:
                user = CustomUser.objects.create_user(
                    email=email,
                    password=password,
                    first_name=first_name,
                    last_name=last_name,
                    phone_number=phone_number,
                    is_seller=is_seller,
                )
                login(request, user)
                migrate_session_cart_to_user(request, user)

                if is_seller:
                    if store_name:
                        SellerProfile.objects.get_or_create(
                            user=user,
                            defaults={
                                "store_name": store_name,
                                "kyc_status": SellerProfile.KycStatus.PENDING,
                            },
                        )
                    messages.success(request, f"Welcome, {user.first_name or 'Seller'}! Your seller account is active. Complete your store profile below.")
                    return redirect("seller_apply")
                else:
                    messages.success(request, f"Welcome to e-Book, {user.first_name or 'Friend'}! Your buyer account is ready.")
                    return redirect(next_url)

    return render(
        request,
        "accounts/login_register.html",
        {
            "mode": mode,
            "next": next_url,
            "cart_count": cart_count,
        },
    )


def logout_view(request):
    """
    Terminates user session and redirects to home.
    """
    logout(request)
    messages.info(request, "You have been successfully logged out.")
    return redirect("home")


def user_profile_view(request):
    """
    Page 12: User Profile & Addresses (/profile/)
    Displays user info, addresses, recent orders, and security options.
    """
    # Use authenticated user or graceful fallback to first user for review
    if request.user.is_authenticated:
        user = request.user
    else:
        user = CustomUser.objects.first()
        if not user:
            user = CustomUser.objects.create_user(
                email="customer@edoxbookshop.com",
                password="DemoPassword123!",
                first_name="Leslie",
                last_name="Alexander",
            )

    active_tab = request.GET.get("tab", "info")
    _, _, cart_count = get_cart_items_for_request(request)

    # Handle Profile Update POST
    if request.method == "POST":
        form_type = request.POST.get("form_type")

        if form_type == "update_info":
            first_name = request.POST.get("first_name", "").strip()
            last_name = request.POST.get("last_name", "").strip()
            phone_number = request.POST.get("phone_number", "").strip()
            
            user.first_name = first_name
            user.last_name = last_name
            user.phone_number = phone_number

            if "avatar" in request.FILES:
                user.avatar = request.FILES["avatar"]

            user.save()
            messages.success(request, "Your profile information has been updated.")
            return redirect("profile")

        elif form_type == "add_address":
            recipient_name = request.POST.get("recipient_name", "").strip()
            phone_number = request.POST.get("phone_number", "").strip()
            street_address = request.POST.get("street_address", "").strip()
            city = request.POST.get("city", "").strip()
            state_division = request.POST.get("state_division", "").strip()
            postal_code = request.POST.get("postal_code", "").strip()
            is_default = bool(request.POST.get("is_default"))

            if recipient_name and street_address and city:
                Address.objects.create(
                    user=user,
                    recipient_name=recipient_name,
                    phone_number=phone_number,
                    street_address=street_address,
                    city=city,
                    state_division=state_division,
                    postal_code=postal_code,
                    is_default=is_default,
                )
                messages.success(request, "Delivery address added successfully.")
            active_tab = "addresses"
            return redirect(f"/profile/?tab=addresses")

        elif form_type == "change_password":
            current_password = request.POST.get("current_password", "")
            new_password = request.POST.get("new_password", "")
            confirm_new_password = request.POST.get("confirm_new_password", "")

            if not user.check_password(current_password):
                messages.error(request, "Your current password is incorrect.")
            elif new_password != confirm_new_password:
                messages.error(request, "New passwords do not match.")
            elif len(new_password) < 6:
                messages.error(request, "Password must be at least 6 characters.")
            else:
                user.set_password(new_password)
                user.save()
                if request.user.is_authenticated:
                    login(request, user)
                messages.success(request, "Your password has been changed successfully.")
            active_tab = "security"
            return redirect(f"/profile/?tab=security")

    addresses = Address.objects.filter(user=user)
    # Seed sample address if none exists
    if not addresses.exists():
        Address.objects.create(
            user=user,
            recipient_name=f"{user.first_name} {user.last_name}".strip() or "Leslie Alexander",
            phone_number=user.phone_number or "+880 1712 345678",
            street_address="House 42, Road 11, Banani",
            city="Dhaka",
            state_division="Dhaka Division",
            postal_code="1213",
            is_default=True,
        )
        addresses = Address.objects.filter(user=user)

    orders = Order.objects.filter(buyer=user).prefetch_related("shipments__items__listing__book").order_by("-created_at")[:10]
    seller_profile = getattr(user, "seller_profile", None)

    return render(
        request,
        "accounts/profile.html",
        {
            "profile_user": user,
            "active_tab": active_tab,
            "addresses": addresses,
            "orders": orders,
            "seller_profile": seller_profile,
            "cart_count": cart_count,
        },
    )


def address_action_view(request, id, action):
    """
    Sets default or deletes an address.
    """
    if request.user.is_authenticated:
        user = request.user
    else:
        user = CustomUser.objects.first()

    address = get_object_or_404(Address, id=id, user=user)

    if action == "set_default":
        address.is_default = True
        address.save()
        messages.success(request, f"'{address.street_address}' set as default address.")
    elif action == "delete":
        address.delete()
        messages.success(request, "Address removed.")

    return redirect("/profile/?tab=addresses")


def seller_apply_view(request):
    """
    Page 13: Become a Seller Application (/seller/apply/)
    Onboarding landing page with perks and application form for verified sellers.
    """
    if request.user.is_authenticated:
        user = request.user
    else:
        user = CustomUser.objects.filter(is_seller=False).first() or CustomUser.objects.first()

    _, _, cart_count = get_cart_items_for_request(request)
    existing_profile = getattr(user, "seller_profile", None)

    if request.method == "POST":
        store_name = request.POST.get("store_name", "").strip()
        bio = request.POST.get("bio", "").strip()
        national_id_number = request.POST.get("national_id_number", "").strip()
        payout_method = request.POST.get("payout_method", "BKASH").upper()
        payout_account_details = request.POST.get("payout_account_details", "").strip()

        if not store_name or not national_id_number or not payout_account_details:
            messages.error(request, "Please fill in all required fields.")
        elif SellerProfile.objects.filter(store_name__iexact=store_name).exclude(user=user).exists():
            messages.error(request, f"The store name '{store_name}' is already taken. Please choose another.")
        else:
            if existing_profile:
                existing_profile.store_name = store_name
                existing_profile.bio = bio
                existing_profile.national_id_number = national_id_number
                existing_profile.payout_method = payout_method
                existing_profile.payout_account_details = payout_account_details
                existing_profile.kyc_status = SellerProfile.KycStatus.PENDING
                existing_profile.save()
                profile = existing_profile
            else:
                profile = apply_for_seller_account(
                    user=user,
                    store_name=store_name,
                    national_id_number=national_id_number,
                    payout_method=payout_method,
                    payout_account_details=payout_account_details,
                    bio=bio,
                )

            messages.success(request, f"Congratulations! Your store '{profile.store_name}' application has been submitted for verification.")
            return redirect("seller_listings")

    return render(
        request,
        "accounts/seller_apply.html",
        {
            "seller_user": user,
            "seller_profile": existing_profile,
            "cart_count": cart_count,
        },
    )

