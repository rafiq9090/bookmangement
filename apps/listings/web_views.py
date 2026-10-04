from decimal import Decimal
import uuid
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.core.paginator import Paginator
from django.db.models import Count, Q, Sum
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.text import slugify
from django.views.decorators.http import require_POST

from apps.accounts.models import CustomUser, SellerProfile
from apps.books.models import Author, Book, Category
from apps.listings.models import BookListing, ListingImage
from apps.orders.models import Order, OrderItem, OrderShipment
from apps.orders.services.cart import get_cart_items_for_request
from apps.payments.models import EscrowHold, PayoutBatch, SellerLedger
from apps.shipping.models import TrackingEvent



def get_authenticated_user(request):
    """
    Returns the signed-in user; anonymous visitors never inherit a seller identity.
    """
    from django.core.exceptions import PermissionDenied
    if not request.user.is_authenticated:
        raise PermissionDenied("Sign in to access seller tools.")
    return request.user


def sell_book_view(request):
    """
    Page 6: Sell Book / Create Listing (/sell/)
    Supports ISBN autofill, physical condition grading, defect notes,
    feature checkboxes, price, author photo upload, and multiple book images (max 5).
    """
    if not request.user.is_authenticated:
        messages.info(request, "Please sign in to list a book for sale.")
        return redirect("/login/?next=/sell/")

    seller = request.user
    categories = Category.objects.all().order_by("name")
    _, _, cart_count = get_cart_items_for_request(request)

    if request.method == "POST":
        from apps.listings.forms import ListingLocationForm, ListingPhotoForm, ListingDetailsForm
        details_form = ListingDetailsForm(request.POST)
        if not details_form.is_valid():
            messages.error(request, str(details_form.errors))
            return redirect(request.path)
        location_form = ListingLocationForm(request.POST)
        for photo in request.FILES.getlist("photos"):
            photo_form = ListingPhotoForm(files={"photo": photo})
            if not photo_form.is_valid():
                messages.error(request, str(photo_form.errors))
                return redirect(request.path)
        if not location_form.is_valid():
            messages.error(request, str(location_form.errors))
            return render(request, "listings/listing_create.html", {"categories": categories, "conditions": BookListing.Condition.choices, "cart_count": cart_count})
        from apps.orders.services.pickup import price_value
        from rest_framework.exceptions import ValidationError
        try:
            price_value(request.POST.get("price"))
            if not request.POST.get("title", "").strip() or request.POST.get("condition") not in BookListing.Condition.values:
                raise ValidationError("Provide a title and a physical condition.")
            if not request.FILES.getlist("photos"):
                raise ValidationError("Upload at least one photo of the actual copy.")
        except ValidationError as exc:
            messages.error(request, str(exc.detail))
            return render(request, "listings/listing_create.html", {"categories": categories, "conditions": BookListing.Condition.choices, "cart_count": cart_count})
        isbn = request.POST.get("isbn", "").strip().replace("-", "")
        title = request.POST.get("title", "").strip()
        author_name = request.POST.get("author", "Independent Author").strip()
        category_id = request.POST.get("category_id")
        price = Decimal(request.POST.get("price", "12.00").strip() or "12.00")
        original_mrp_str = request.POST.get("original_mrp", "").strip()
        original_mrp = details_form.cleaned_data["original_mrp"]
        condition = request.POST.get("condition", BookListing.Condition.GOOD)
        condition_notes = request.POST.get("condition_notes", "").strip()
        edition_year_str = request.POST.get("edition_year", "").strip()
        edition_year = int(edition_year_str) if edition_year_str.isdigit() else None
        is_hardcover = bool(request.POST.get("is_hardcover"))
        has_dust_jacket = bool(request.POST.get("has_dust_jacket"))
        is_signed_by_author = bool(request.POST.get("is_signed_by_author"))

        with transaction.atomic():
            author_id = request.POST.get("author_id", "").strip()
            author = None
            if author_id and author_id.isdigit():
                author = Author.objects.filter(id=int(author_id)).first()
            if not author and author_name:
                author = Author.objects.filter(name__iexact=author_name).first()
            if not author:
                base_slug = slugify(author_name) or "author"
                unique_slug = base_slug
                counter = 1
                while Author.objects.filter(slug=unique_slug).exists():
                    unique_slug = f"{base_slug}-{counter}"
                    counter += 1
                author = Author.objects.create(
                    name=author_name or "Independent Author",
                    slug=unique_slug,
                )

            # Handle author photo upload if provided by seller
            author_photo = request.FILES.get("author_photo")
            if author_photo and seller.is_staff:
                author.photo = author_photo
                author.save(update_fields=["photo"])

            if category_id:
                category = Category.objects.filter(id=category_id).first()
            else:
                category = Category.objects.first()

            metadata = {
                "title": title or "Untitled Book",
                "slug": slugify(title or "untitled-book") + f"-{uuid.uuid4().hex[:10]}",
                "publication_year": edition_year,
            }
            if len(isbn) == 13:
                book, created = Book.objects.get_or_create(isbn_13=isbn, defaults=metadata)
            elif len(isbn) == 10:
                book = Book.objects.filter(isbn_10=isbn).first()
                created = book is None
                if created:
                    book = Book.objects.create(isbn_10=isbn, **metadata)
            else:
                book, created = Book.objects.create(**metadata), True
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
                **location_form.cleaned_data,
            )

            # Upload up to 5 book images
            photos = request.FILES.getlist("photos")
            for i, photo in enumerate(photos[:5]):
                ListingImage.objects.create(
                    listing=listing,
                    image=photo,
                    is_primary=(i == 0),
                )

            # Sync primary cover image to book catalog if empty
            if not book.cover_image and listing.images.exists():
                primary = listing.images.filter(is_primary=True).first() or listing.images.first()
                if primary and primary.image:
                    book.cover_image = primary.image
                    book.save(update_fields=["cover_image"])

        CustomUser.objects.filter(pk=seller.pk).update(is_seller=True)
        messages.success(request, f'Book "{book.title}" listed successfully with {min(len(photos), 5)} photo(s)!')
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


def author_autocomplete_api(request):
    """
    AJAX helper for author autocomplete.
    Returns authors matching ?q= query with their photo URL, book count,
    and checks for exact name matches for auto-setting author portrait.
    """
    query = request.GET.get("q", "").strip()
    if not query:
        authors = Author.objects.annotate(book_count=Count("books")).order_by("-book_count", "name")[:8]
    else:
        authors = Author.objects.filter(name__icontains=query).annotate(book_count=Count("books")).order_by("-book_count", "name")[:8]

    results = []
    exact_match = None
    for a in authors:
        photo_url = a.photo.url if a.photo else ""
        item = {
            "id": a.id,
            "name": a.name,
            "photo_url": photo_url,
            "has_photo": bool(photo_url),
            "book_count": a.book_count,
        }
        results.append(item)
        if query and a.name.lower() == query.lower():
            exact_match = item

    # If query had no exact match in the top 8, check if exact match exists in DB
    if query and not exact_match:
        exact_author = Author.objects.filter(name__iexact=query).first()
        if exact_author:
            photo_url = exact_author.photo.url if exact_author.photo else ""
            exact_match = {
                "id": exact_author.id,
                "name": exact_author.name,
                "photo_url": photo_url,
                "has_photo": bool(photo_url),
                "book_count": exact_author.books.count(),
            }

    return JsonResponse({"results": results, "exact_match": exact_match})


def isbn_lookup_api(request):
    """
    AJAX helper for ISBN lookup to autofill title, author, author photo, and category.
    Searches local catalog first, and falls back to OpenLibrary API if not yet catalogued.
    """
    isbn = request.GET.get("isbn", "").strip().replace("-", "")
    if not isbn:
        return JsonResponse({"found": False})

    # 1. Local Database Lookup
    book = Book.objects.filter(Q(isbn_10=isbn) | Q(isbn_13=isbn)).prefetch_related("authors", "categories").first()

    # 2. External OpenLibrary API Lookup Fallback
    if not book:
        try:
            from apps.books.services.openlibrary import fetch_or_create_book_by_isbn
            book = fetch_or_create_book_by_isbn(isbn)
        except Exception:
            book = None

    if book:
        first_author = book.authors.first()
        return JsonResponse(
            {
                "found": True,
                "title": book.title,
                "author": first_author.name if first_author else "",
                "author_photo_url": first_author.photo.url if (first_author and first_author.photo) else "",
                "category_id": book.categories.first().id if book.categories.exists() else None,
                "publication_year": book.publication_year,
            }
        )
    return JsonResponse({"found": False})


@login_required(login_url="/login/")
def seller_listings_view(request):
    """
    Page 7: Seller Dashboard / My Listings (/seller/listings/)
    Displays active, reserved, sold, and draft listings with inventory metrics.
    """
    seller = get_authenticated_user(request)
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

    listings = Paginator(listings, 25).get_page(request.GET.get("page"))
    _, _, cart_count = get_cart_items_for_request(request)

    return render(
        request,
        "listings/my_listings.html",
        {
            "listings": listings,
            "page_obj": listings,
            "current_status": status_filter,
            "query": query,
            "total_listings": total_listings,
            "active_count": active_count,
            "sold_count": sold_count,
            "total_revenue": total_revenue,
            "cart_count": cart_count,
        },
    )


@login_required(login_url="/login/")
@require_POST
@transaction.atomic
def mark_listing_sold_view(request, id):
    """Record a sale outside the platform without completing a buyer's transaction."""
    listing = get_object_or_404(
        BookListing.objects.select_for_update(), id=id, seller=request.user, is_deleted=False
    )
    if listing.status == BookListing.Status.SOLD:
        messages.info(request, "This book is already marked as sold.")
        return redirect("seller_listings")
    has_pickup = listing.agreements.filter(status__in=[
        "AWAITING_CONFIRMATION", "DISPUTED"
    ]).exists()
    has_order = listing.order_items.exclude(shipment__order__status=Order.Status.CANCELLED).exists()
    if has_pickup or has_order:
        messages.error(request, "Complete or cancel this book's existing pickup or checkout before marking it sold manually.")
        return redirect("seller_listings")
    reservations = listing.agreements.filter(status__in=["RESERVED", "PICKUP_AGREED"])
    if reservations.exists() and request.POST.get("cancel_reservation") != "yes":
        messages.error(request, "This book has a reserved pickup. Confirm cancellation before marking it sold.")
        return redirect("seller_listings")
    from apps.orders.services.pickup import act_on_agreement
    for agreement in reservations:
        act_on_agreement(agreement.pk, request.user, "cancel")
    listing.status = BookListing.Status.SOLD
    listing.save(update_fields=["status", "updated_at"])
    listing.cart_items.all().delete()
    messages.success(request, f'"{listing.book.title}" marked as sold.')
    return redirect("seller_listings")


@transaction.atomic
def toggle_listing_view(request, id):
    """
    Toggles a listing between ACTIVE and ARCHIVED.
    """
    if not request.user.is_authenticated:
        return redirect("/login/?next=/seller/dashboard/?tab=listings")
    seller = request.user
    listing = get_object_or_404(BookListing.objects.select_for_update(), id=id, seller=seller)
    if request.method != "POST" or listing.status in (BookListing.Status.RESERVED, BookListing.Status.SOLD):
        messages.error(request, "Reserved or sold copies cannot be reactivated.")
        return redirect("seller_listings")
    if listing.status == BookListing.Status.ACTIVE:
        listing.status = BookListing.Status.ARCHIVED
    else:
        listing.status = BookListing.Status.ACTIVE
    listing.save(update_fields=["status", "updated_at"])
    return redirect("seller_listings")


@transaction.atomic
def edit_listing_view(request, id):
    """
    Allows a seller to edit an existing book listing: title, author, category, price,
    condition, notes, edition year, features, status, and photos.
    """
    if not request.user.is_authenticated:
        messages.info(request, "Please sign in to edit your listings.")
        return redirect(f"/login/?next=/seller/listings/{id}/edit/")

    listing = get_object_or_404(
        BookListing.objects.select_for_update().select_related("book").prefetch_related("images", "book__authors", "book__categories"),
        id=id,
        seller=request.user,
        is_deleted=False,
    )
    categories = Category.objects.all().order_by("name")
    _, _, cart_count = get_cart_items_for_request(request)

    if request.method == "POST":
        from apps.listings.forms import ListingLocationForm, ListingPhotoForm, ListingDetailsForm
        details_form = ListingDetailsForm(request.POST)
        if not details_form.is_valid():
            messages.error(request, str(details_form.errors))
            return redirect(request.path)
        location_form = ListingLocationForm(request.POST)
        for photo in request.FILES.getlist("photos"):
            photo_form = ListingPhotoForm(files={"photo": photo})
            if not photo_form.is_valid():
                messages.error(request, str(photo_form.errors))
                return redirect(request.path)
        if not location_form.is_valid():
            messages.error(request, str(location_form.errors))
            return redirect("edit_listing", id=listing.pk)
        from apps.orders.services.pickup import price_value
        from rest_framework.exceptions import ValidationError
        try:
            price_value(request.POST.get("price", listing.price))
            if request.POST.get("condition", listing.condition) not in BookListing.Condition.values:
                raise ValidationError("Choose a physical condition for this copy.")
        except ValidationError as exc:
            messages.error(request, str(exc.detail))
            return redirect("edit_listing", id=listing.pk)
        title = request.POST.get("title", "").strip()
        author_name = request.POST.get("author", "").strip()
        category_id = request.POST.get("category_id")
        price_str = request.POST.get("price", "").strip()
        original_mrp_str = request.POST.get("original_mrp", "").strip()
        condition = request.POST.get("condition", listing.condition)
        condition_notes = request.POST.get("condition_notes", "").strip()
        edition_year_str = request.POST.get("edition_year", "").strip()
        status = request.POST.get("status", listing.status)
        editable_statuses = [BookListing.Status.ACTIVE, BookListing.Status.ARCHIVED, BookListing.Status.DRAFT, BookListing.Status.SOLD]
        if status not in editable_statuses:
            messages.error(request, "Choose Active, Archived, Draft, or Sold. Reservations are managed through pickup agreements.")
            return redirect("edit_listing", id=listing.pk)
        cancel_reservations = False
        if listing.status == BookListing.Status.RESERVED:
            if status == listing.status or request.POST.get("cancel_reservation") != "yes":
                messages.error(request, "Choose a new status and confirm cancellation of the reserved pickup before saving.")
                return redirect("edit_listing", id=listing.pk)
            cancel_reservations = True
        if status != listing.status:
            protected_statuses = ["AWAITING_CONFIRMATION", "DISPUTED", "COMPLETED"]
            if not cancel_reservations:
                protected_statuses += ["RESERVED", "PICKUP_AGREED"]
            has_transaction = listing.agreements.filter(status__in=protected_statuses).exists() or listing.order_items.exclude(shipment__order__status=Order.Status.CANCELLED).exists()
            if has_transaction:
                messages.error(request, "This copy has a pickup or sale record. Manage its status through that transaction; list another copy separately.")
                return redirect("edit_listing", id=listing.pk)

        is_hardcover = bool(request.POST.get("is_hardcover"))
        has_dust_jacket = bool(request.POST.get("has_dust_jacket"))
        is_signed_by_author = bool(request.POST.get("is_signed_by_author"))

        try:
            price = Decimal(price_str) if price_str else listing.price
        except Exception:
            price = listing.price

        original_mrp = details_form.cleaned_data["original_mrp"]

        edition_year = int(edition_year_str) if edition_year_str.isdigit() else None
        if (edition_year_str and (edition_year is None or not 1 <= edition_year <= 9999)) or (original_mrp is not None and not original_mrp.is_finite()):
            messages.error(request, "Provide a valid edition year and original price.")
            return redirect("edit_listing", id=listing.pk)
        if original_mrp is not None and not Decimal("0") <= original_mrp <= Decimal("999999.99"):
            messages.error(request, "Original price must be between 0 and 999999.99.")
            return redirect("edit_listing", id=listing.pk)

        with transaction.atomic():
            if cancel_reservations:
                from apps.orders.services.pickup import act_on_agreement
                for agreement in listing.agreements.filter(status__in=["RESERVED", "PICKUP_AGREED"]):
                    act_on_agreement(agreement.pk, request.user, "cancel")
            book = listing.book
            # Canonical catalog records are shared across sellers.
            if request.user.is_staff:
                if title and title != book.title:
                    book.title = title
                    book.save(update_fields=["title"])

                if author_name:
                    author, _ = Author.objects.get_or_create(
                        name=author_name,
                        defaults={"slug": (slugify(author_name) or "author")[:200] + "-" + uuid.uuid4().hex[:8]},
                    )
                    if not book.authors.filter(id=author.id).exists():
                        book.authors.clear()
                        book.authors.add(author)

                if category_id:
                    category = Category.objects.filter(id=category_id).first()
                    if category and not book.categories.filter(id=category.id).exists():
                        book.categories.clear()
                        book.categories.add(category)


            for field, value in location_form.cleaned_data.items():
                setattr(listing, field, value)
            listing.condition_needs_review = False
            listing.price = price
            listing.original_mrp = original_mrp
            listing.condition = condition
            listing.condition_notes = condition_notes
            listing.edition_year = edition_year
            listing.is_hardcover = is_hardcover
            listing.has_dust_jacket = has_dust_jacket
            listing.is_signed_by_author = is_signed_by_author
            listing.status = status
            if status != BookListing.Status.ACTIVE:
                listing.cart_items.all().delete()
            listing.save()

            # Handle photo deletion
            delete_photo_ids = request.POST.getlist("delete_photos")
            if delete_photo_ids:
                listing.images.filter(id__in=delete_photo_ids).delete()

            # Handle new photo uploads
            new_photos = request.FILES.getlist("photos")
            current_count = listing.images.count()
            for i, photo in enumerate(new_photos[:max(0, 5 - current_count)]):
                ListingImage.objects.create(
                    listing=listing,
                    image=photo,
                    is_primary=(current_count == 0 and i == 0),
                )

            # A seller's cover upload belongs to this physical copy, not the catalog.
            cover_photo = request.FILES.get("cover_image")
            if cover_photo:
                if listing.images.count() >= 5:
                    primary = listing.images.filter(is_primary=True).first() or listing.images.first()
                    primary.image = cover_photo
                    primary.is_primary = True
                    primary.save(update_fields=["image", "is_primary"])
                    listing.images.exclude(pk=primary.pk).update(is_primary=False)
                else:
                    listing.images.update(is_primary=False)
                    ListingImage.objects.create(listing=listing, image=cover_photo, is_primary=True)

        messages.success(request, f'Listing for "{listing.book.title}" updated successfully.')
        return redirect("seller_listings")

    return render(
        request,
        "listings/listing_edit.html",
        {
            "listing": listing,
            "categories": categories,
            "conditions": BookListing.Condition.choices,
            "statuses": [(value, label) for value, label in BookListing.Status.choices if value != BookListing.Status.RESERVED or listing.status == value],
            "cart_count": cart_count,
        },
    )


def seller_dashboard_view(request, tab=None):
    """
    Page: Unified All-in-One Seller Dashboard (/seller/dashboard/)
    Consolidates:
      1. Overview: KPIs, recent shipments, balance, recent books
      2. My Listings: Inventory management, status filters, search, toggle, edit price
      3. Shipments: Courier dispatch (Steadfast / Pathao), tracking events
      4. Wallet & Payouts: Escrow balance, withdrawal requests, ledger
      5. Store Settings: Store profile, phone, KYC verification status
    """
    if not request.user.is_authenticated:
        messages.info(request, "Please sign in with your seller account to access the Seller Dashboard.")
        return redirect("/login/?next=/seller/dashboard/")

    from django.conf import settings
    if settings.LOCAL_PICKUP_ENABLED:
        return seller_listings_view(request)
    if not request.user.is_seller:
        messages.warning(request, "You need a registered seller account to access the Seller Dashboard.")
        return redirect("seller_apply")

    seller = request.user
    active_tab = tab or request.GET.get("tab", "overview").lower()
    if active_tab not in ["overview", "listings", "shipments", "wallet", "settings"]:
        active_tab = "overview"

    # Profile & KYC
    profile, _ = SellerProfile.objects.get_or_create(
        user=seller,
        defaults={"store_name": f"Reader {seller.pk} Book Store"},
    )

    # Handle POST Actions
    if request.method == "POST":
        action = request.POST.get("action")

        # 1. Courier Dispatch Handover
        if action == "dispatch_shipment" or "shipment_id" in request.POST:
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
                location=f"{profile.store_name} Fulfillment Hub",
            )
            messages.success(request, f"Order marked dispatched with {courier_name} (Tracking: {tracking_num})")
            return redirect("/seller/dashboard/?tab=shipments")

        # 2. Payout Withdrawal Request
        elif action == "request_payout":
            amount_str = request.POST.get("amount", "0").strip()
            payout_method = request.POST.get("payout_method", "BKASH")
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
                messages.success(request, f"Payout request for ৳{amount} submitted successfully via {payout_method}.")
            else:
                messages.error(request, "Please enter a valid amount and account details for payout.")
            return redirect("/seller/dashboard/?tab=wallet")

        # 3. Store Settings Update
        elif action == "update_settings":
            store_name = request.POST.get("store_name", "").strip()
            bio = request.POST.get("bio", "").strip()
            phone_number = request.POST.get("phone_number", "").strip()
            payout_method = request.POST.get("payout_method", "BKASH")
            payout_account_details = request.POST.get("payout_account_details", "").strip()

            if store_name:
                profile.store_name = store_name
            profile.bio = bio
            profile.payout_method = payout_method
            profile.payout_account_details = payout_account_details
            profile.save()

            if phone_number:
                seller.phone_number = phone_number
                seller.save(update_fields=["phone_number"])

            messages.success(request, "Store profile and settings updated successfully!")
            return redirect("/seller/dashboard/?tab=settings")

        # 4. Quick Price Update for Listing
        elif action == "update_price":
            listing_id = request.POST.get("listing_id")
            new_price_str = request.POST.get("price", "").strip()
            listing = get_object_or_404(BookListing, id=listing_id, seller=seller)
            try:
                new_price = Decimal(new_price_str)
                if new_price > 0:
                    listing.price = new_price
                    listing.save(update_fields=["price", "updated_at"])
                    messages.success(request, f"Price for '{listing.book.title}' updated to ৳{new_price}.")
            except Exception:
                messages.error(request, "Invalid price entered.")
            return redirect("/seller/dashboard/?tab=listings")

    # Metrics & Inventory
    all_seller_listings = BookListing.objects.filter(seller=seller, is_deleted=False).select_related("book").prefetch_related("images", "book__authors")
    total_listings = all_seller_listings.count()
    active_count = all_seller_listings.filter(status=BookListing.Status.ACTIVE).count()
    sold_count = all_seller_listings.filter(status=BookListing.Status.SOLD).count()
    reserved_count = all_seller_listings.filter(status=BookListing.Status.RESERVED).count()

    # Financials (Real-time dynamic calculation)
    gross_sales = OrderItem.objects.filter(
        shipment__seller=seller,
        shipment__order__status__in=[Order.Status.PAID, Order.Status.PROCESSING, Order.Status.COMPLETED],
    ).aggregate(total=Sum("price_at_purchase"))["total"] or Decimal("0.00")

    credits = SellerLedger.objects.filter(
        seller=seller,
        entry_type=SellerLedger.EntryType.SALE_CREDIT,
    ).aggregate(total=Sum("amount"))["total"] or Decimal("0.00")

    total_revenue = max(gross_sales, credits)

    debits = SellerLedger.objects.filter(
        seller=seller,
        entry_type__in=[
            SellerLedger.EntryType.PLATFORM_FEE,
            SellerLedger.EntryType.PAYOUT_DEBIT,
            SellerLedger.EntryType.REFUND_DEBIT,
        ],
    ).aggregate(total=Sum("amount"))["total"] or Decimal("0.00")

    available_balance = max(Decimal("0.00"), credits - debits)

    escrow_agg = EscrowHold.objects.filter(
        shipment__seller=seller,
        status=EscrowHold.EscrowStatus.HELD,
    ).aggregate(total=Sum("seller_net_amount"))
    escrow_balance = escrow_agg["total"] or Decimal("0.00")

    # Shipments
    all_shipments = OrderShipment.objects.filter(seller=seller).select_related("order", "order__buyer").prefetch_related("items__listing__book").order_by("-order__created_at")
    waiting_shipments_count = all_shipments.filter(status=OrderShipment.ShipmentStatus.WAITING_SELLER).count()
    in_transit_count = all_shipments.filter(status=OrderShipment.ShipmentStatus.IN_TRANSIT).count()
    delivered_count = all_shipments.filter(status=OrderShipment.ShipmentStatus.DELIVERED).count()

    # Tab: Listings Filter
    listings = all_seller_listings
    status_filter = request.GET.get("status", "ALL").upper()
    query = request.GET.get("q", "").strip()
    if status_filter != "ALL":
        listings = listings.filter(status=status_filter)
    if query:
        listings = listings.filter(Q(book__title__icontains=query) | Q(book__isbn_13__icontains=query))

    # Tab: Shipments Filter
    shipment_status_filter = request.GET.get("shipment_status", "ALL").upper()
    filtered_shipments = all_shipments
    if shipment_status_filter != "ALL":
        filtered_shipments = filtered_shipments.filter(status=shipment_status_filter)

    # Tab: Wallet Data
    ledger_entries = SellerLedger.objects.filter(seller=seller).order_by("-created_at")[:25]
    payout_requests = PayoutBatch.objects.filter(seller=seller).order_by("-created_at")[:15]

    # Overview Activity
    recent_shipments = all_shipments[:5]
    recent_listings = all_seller_listings[:5]

    _, _, cart_count = get_cart_items_for_request(request)

    return render(
        request,
        "listings/seller_dashboard.html",
        {
            "seller": seller,
            "profile": profile,
            "active_tab": active_tab,
            # Inventory & Stats
            "total_listings": total_listings,
            "active_count": active_count,
            "sold_count": sold_count,
            "reserved_count": reserved_count,
            "listings": listings,
            "current_status": status_filter,
            "query": query,
            # Financials
            "total_revenue": total_revenue,
            "available_balance": available_balance,
            "escrow_balance": escrow_balance,
            "ledger_entries": ledger_entries,
            "payout_requests": payout_requests,
            # Shipments
            "all_shipments": filtered_shipments,
            "shipment_status_filter": shipment_status_filter,
            "waiting_shipments_count": waiting_shipments_count,
            "in_transit_count": in_transit_count,
            "delivered_count": delivered_count,
            # Overview
            "recent_shipments": recent_shipments,
            "recent_listings": recent_listings,
            "cart_count": cart_count,
        },
    )
