from collections import defaultdict
from decimal import Decimal
import uuid
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, redirect, render
from apps.accounts.models import CustomUser
from apps.books.models import Book, Category
from apps.listings.models import BookListing
from apps.orders.models import Cart, CartItem, Order, OrderItem, OrderShipment


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


def home_view(request):
    """
    Renders the modern storefront homepage, passing real database categories,
    active book listings, and user cart status to the template.
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

    _, _, cart_count = get_cart_items_for_request(request)

    return render(
        request,
        "home.html",
        {
            "categories": categories,
            "listings": listings,
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


def checkout_view(request):
    """
    Renders the Checkout page and processes order placement.
    """
    items, subtotal, cart_count = get_cart_items_for_request(request)
    if not items:
        return redirect("cart")

    shipping_fee = Decimal("2.00") if subtotal > 0 and subtotal < Decimal("30.00") else Decimal("0.00")
    total = subtotal + shipping_fee

    if request.method == "POST":
        full_name = request.POST.get("full_name", "Valued Customer").strip()
        phone_number = request.POST.get("phone_number", "").strip()
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

        if request.user.is_authenticated:
            buyer = request.user
        else:
            email = request.POST.get("email", "").strip() or "customer@edoxbookshop.com"
            buyer, _ = CustomUser.objects.get_or_create(
                email=email,
                defaults={"first_name": full_name},
            )

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

