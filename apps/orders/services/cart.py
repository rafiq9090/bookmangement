from decimal import Decimal
from apps.listings.models import BookListing
from apps.orders.models import Cart, CartItem


def get_cart_items_for_request(request):
    """
    Returns (items_list, subtotal, cart_count) for authenticated users.
    Unauthenticated users have an empty cart.
    """
    if not request.user.is_authenticated:
        return [], Decimal("0.00"), 0

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


def migrate_session_cart_to_user(request, user):
    """
    Transfers items from anonymous guest session cart to authenticated user's DB cart.
    Safely handles OneToOneField uniqueness constraint on listing.
    """
    session_cart_ids = request.session.get("cart_items", [])
    if session_cart_ids:
        cart, _ = Cart.objects.get_or_create(user=user)
        for listing_id in session_cart_ids:
            listing = BookListing.objects.filter(id=listing_id, status=BookListing.Status.ACTIVE, is_deleted=False).first()
            if listing:
                # Do not add seller's own listing to their cart
                if listing.seller_id == user.id:
                    continue

                existing_item = CartItem.objects.filter(listing=listing).first()
                if existing_item:
                    if existing_item.cart_id != cart.id:
                        existing_item.cart = cart
                        existing_item.save(update_fields=["cart"])
                else:
                    CartItem.objects.create(cart=cart, listing=listing)
        request.session["cart_items"] = []
        if hasattr(request.session, "modified"):
            request.session.modified = True

