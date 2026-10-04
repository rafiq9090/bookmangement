from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.contrib.auth import views as auth_views
from django.urls import include, path, re_path
from django.views.generic import TemplateView
from drf_spectacular.views import SpectacularAPIView, SpectacularRedocView, SpectacularSwaggerView
# Web Frontend Views (Modular App Architecture)
from apps.accounts.web_views import (
    address_action_view,
    login_register_view,
    logout_view,
    seller_apply_view,
    user_profile_view,
)
from apps.accounts.platform_admin_views import (
    platform_admin_dashboard_view,
    platform_admin_login_view,
)
from apps.books.web_views import (
    authors_list_view,
    book_detail_view,
    home_view,
    location_autocomplete_api,
    location_reverse_api,
    store_view,
)
from apps.listings.web_views import (
    author_autocomplete_api,
    edit_listing_view,
    isbn_lookup_api,
    sell_book_view,
    seller_dashboard_view,
    seller_listings_view,
    toggle_listing_view,
    mark_listing_sold_view,
)
from apps.orders.web_views import (
    add_to_cart_view,
    cancel_order_view,
    cart_view,
    checkout_view,
    order_detail_view,
    remove_from_cart_view,
)
from apps.messaging.web_views import (
    conversation_detail_view,
    conversation_messages_api,
    inbox_threads_api,
    inbox_unread_count_api,
    inbox_view,
    proceed_to_checkout_from_chat,
    start_inquiry_view,
)
from apps.payments.web_views import seller_wallet_view
from apps.shipping.web_views import parcel_tracking_view, seller_shipments_view

from apps.orders.pickup_views import (pickup_list, pickup_detail, request_purchase, report_listing, AgreementListAPI, AgreementDetailAPI, resolve_pickup)

from config.health import health
from apps.accounts.cookie_views import cookie_preferences
from apps.accounts.contact_views import contact
from apps.books.recommendation_views import recommendation_preferences
from apps.accounts.push_views import service_worker, push_config, push_subscription
from config.error_views import page_not_found

handler404 = "config.error_views.page_not_found"

urlpatterns = [
    path("404/", page_not_found, name="page_not_found"),
    path("contact/", contact, name="contact"),
    path("privacy/", TemplateView.as_view(template_name="pages/privacy.html"), name="privacy"),
    path("about/", TemplateView.as_view(template_name="pages/about.html"), name="about"),
    path("cookies/preferences/", cookie_preferences, name="cookie_preferences"),
    path("recommendations/preferences/", recommendation_preferences, name="recommendation_preferences"),
    path("push-worker.js", service_worker, name="push_worker"),
    path("notifications/push/config/", push_config, name="push_config"),
    path("notifications/push/subscription/", push_subscription, name="push_subscription"),
    path("health/", health, name="health"),
    path("moderation/pickups/<int:pk>/", resolve_pickup, name="resolve_pickup"),
    path("password-reset/", auth_views.PasswordResetView.as_view(), name="password_reset"),
    path("password-reset/done/", auth_views.PasswordResetDoneView.as_view(), name="password_reset_done"),
    path("reset/<uidb64>/<token>/", auth_views.PasswordResetConfirmView.as_view(), name="password_reset_confirm"),
    path("reset/done/", auth_views.PasswordResetCompleteView.as_view(), name="password_reset_complete"),
    path("pickups/", pickup_list, name="pickup_list"),
    path("pickups/<int:pk>/", pickup_detail, name="pickup_detail"),
    path("listings/<int:listing_id>/request/", request_purchase, name="request_purchase"),
    path("listings/<int:listing_id>/report/", report_listing, name="report_listing"),
    path("api/v1/pickups/", AgreementListAPI.as_view(), name="pickup-api-list"),
    path("api/v1/pickups/<int:pk>/", AgreementDetailAPI.as_view(), name="pickup-api-detail"),
    path("api/locations/suggest/", location_autocomplete_api, name="location_autocomplete_api"),
    path("api/locations/reverse/", location_reverse_api, name="location_reverse_api"),
    path("", home_view, name="home"),
    path("store/", store_view, name="store"),
    path("inbox/", inbox_view, name="inbox"),
    path("inbox/api/unread/", inbox_unread_count_api, name="inbox_unread_count_api"),
    path("inbox/api/threads/", inbox_threads_api, name="inbox_threads_api"),
    path("inbox/<int:conversation_id>/", conversation_detail_view, name="conversation_detail"),
    path("inbox/<int:conversation_id>/api/messages/", conversation_messages_api, name="conversation_messages_api"),
    path("inbox/<int:conversation_id>/checkout/", proceed_to_checkout_from_chat, name="proceed_to_checkout_from_chat"),
    path("listings/<int:listing_id>/inquire/", start_inquiry_view, name="start_inquiry"),
    path("authors/", authors_list_view, name="authors_list"),
    path("books/<slug:slug>/", book_detail_view, name="book_detail"),
    path("cart/", cart_view, name="cart"),
    path("cart/add/<int:listing_id>/", add_to_cart_view, name="add_to_cart"),
    path("cart/remove/<int:item_id>/", remove_from_cart_view, name="remove_from_cart"),
    path("checkout/", checkout_view, name="checkout"),
    path("orders/<uuid:id>/", order_detail_view, name="order_detail"),
    path("orders/<uuid:id>/cancel/", cancel_order_view, name="cancel_order"),
    
    # Unified Seller Dashboard & Marketplace Flow
    path("seller/dashboard/", seller_dashboard_view, name="seller_dashboard"),
    path("sell/", sell_book_view, name="sell_book"),
    path("seller/lookup-isbn/", isbn_lookup_api, name="isbn_lookup"),
    path("seller/authors/suggest/", author_autocomplete_api, name="author_autocomplete"),
    path("seller/listings/", seller_dashboard_view, {"tab": "listings"}, name="seller_listings"),
    path("seller/listings/<int:id>/edit/", edit_listing_view, name="edit_listing"),
    path("seller/listings/<int:id>/toggle/", toggle_listing_view, name="toggle_listing"),
    path("seller/listings/<int:id>/sold/", mark_listing_sold_view, name="mark_listing_sold"),
    path("seller/wallet/", seller_dashboard_view, {"tab": "wallet"}, name="seller_wallet"),
    path("seller/shipments/", seller_dashboard_view, {"tab": "shipments"}, name="seller_shipments"),
    path("tracking/", parcel_tracking_view, name="parcel_tracking"),
    path("tracking/<str:tracking_number>/", parcel_tracking_view, name="parcel_tracking_detail"),

    # User Authentication & Profile (Pages 11 - 13)
    path("login/", login_register_view, name="login"),
    path("register/", login_register_view, name="register"),
    path("logout/", logout_view, name="logout"),
    path("profile/", user_profile_view, name="profile"),
    path("profile/addresses/<int:id>/<str:action>/", address_action_view, name="address_action"),
    path("seller/apply/", seller_apply_view, name="seller_apply"),

    # Dedicated Modern Marketplace Platform Admin Dashboard & Admin Login
    path("admin-login/", platform_admin_login_view, name="platform_admin_login"),
    path("admin/dashboard/", platform_admin_dashboard_view, name="platform_admin_dashboard"),
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
    # Preview the branded error for unmatched local URLs without disabling debugging.
    urlpatterns += [re_path(r"^.*$", page_not_found)]
