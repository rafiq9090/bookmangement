from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path
from drf_spectacular.views import SpectacularAPIView, SpectacularRedocView, SpectacularSwaggerView

urlpatterns = [
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
