from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path
from drf_spectacular.views import SpectacularAPIView, SpectacularRedocView, SpectacularSwaggerView
# Web Frontend Views (Modular App Architecture)
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
    isbn_lookup_api,
    sell_book_view,
    seller_listings_view,
    toggle_listing_view,
)
from apps.orders.web_views import (
    add_to_cart_view,
    cart_view,
    checkout_view,
    order_detail_view,
    remove_from_cart_view,
)
from apps.payments.web_views import seller_wallet_view
from apps.shipping.web_views import parcel_tracking_view, seller_shipments_view

urlpatterns = [
    path("", home_view, name="home"),
    path("store/", store_view, name="store"),
    path("books/<slug:slug>/", book_detail_view, name="book_detail"),
    path("cart/", cart_view, name="cart"),
    path("cart/add/<int:listing_id>/", add_to_cart_view, name="add_to_cart"),
    path("cart/remove/<int:item_id>/", remove_from_cart_view, name="remove_from_cart"),
    path("checkout/", checkout_view, name="checkout"),
    path("orders/<uuid:id>/", order_detail_view, name="order_detail"),
    
    # Marketplace & Seller Flow (Pages 6 - 10)
    path("sell/", sell_book_view, name="sell_book"),
    path("seller/lookup-isbn/", isbn_lookup_api, name="isbn_lookup"),
    path("seller/listings/", seller_listings_view, name="seller_listings"),
    path("seller/listings/<int:id>/toggle/", toggle_listing_view, name="toggle_listing"),
    path("seller/wallet/", seller_wallet_view, name="seller_wallet"),
    path("seller/shipments/", seller_shipments_view, name="seller_shipments"),
    path("tracking/", parcel_tracking_view, name="parcel_tracking"),
    path("tracking/<str:tracking_number>/", parcel_tracking_view, name="parcel_tracking_detail"),

    # User Authentication & Profile (Pages 11 - 13)
    path("login/", login_register_view, name="login"),
    path("register/", login_register_view, name="register"),
    path("logout/", logout_view, name="logout"),
    path("profile/", user_profile_view, name="profile"),
    path("profile/addresses/<int:id>/<str:action>/", address_action_view, name="address_action"),
    path("seller/apply/", seller_apply_view, name="seller_apply"),

    path("admin/", admin.site.urls),
    
    # OpenAPI Documentation
    path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
    path("api/docs/", SpectacularSwaggerView.as_view(url_name="schema"), name="swagger-ui"),
    path("api/redoc/", SpectacularRedocView.as_view(url_name="schema"), name="redoc"),

    # API v1 Namespaces
    path("api/v1/accounts/", include("apps.accounts.urls", namespace="accounts")),
    path("api/v1/books/", include("apps.books.urls", namespace="books")),
    path("api/v1/listings/", include("apps.listings.urls", namespace="listings")),
    path("api/v1/orders/", include("apps.orders.urls", namespace="orders")),
    path("api/v1/payments/", include("apps.payments.urls", namespace="payments")),
    path("api/v1/shipping/", include("apps.shipping.urls", namespace="shipping")),
    path("api/v1/messaging/", include("apps.messaging.urls", namespace="messaging")),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
