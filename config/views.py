"""
Central Web View Router (Backward Compatibility Module).
All frontend web views have been cleanly modularized into their respective Django apps:
- apps/books/web_views.py
- apps/orders/web_views.py
- apps/listings/web_views.py
- apps/payments/web_views.py
- apps/shipping/web_views.py
- apps/accounts/web_views.py
"""

from apps.accounts.web_views import (
    address_action_view,
    login_register_view,
    logout_view,
    seller_apply_view,
    user_profile_view,
)
from apps.books.web_views import (
    book_detail_view,
    home_view,
    store_view,
)
from apps.listings.web_views import (
    get_or_create_seller_user,
    isbn_lookup_api,
    sell_book_view,
    seller_listings_view,
    toggle_listing_view,
)
from apps.orders.services.cart import (
    get_cart_items_for_request,
    migrate_session_cart_to_user,
)
from apps.orders.web_views import (
    add_to_cart_view,
    cart_view,
    checkout_view,
    order_detail_view,
    remove_from_cart_view,
)
from apps.payments.web_views import seller_wallet_view
from apps.shipping.web_views import (
    parcel_tracking_view,
    seller_shipments_view,
)
