from django.urls import path
from apps.listings.views import (
    ListingDetailView,
    ListingImageUploadView,
    ListingListCreateView,
    SellerMyListingsView,
)

app_name = "listings"

urlpatterns = [
    path("", ListingListCreateView.as_view(), name="list-create"),
    path("my/", SellerMyListingsView.as_view(), name="my-listings"),
    path("<int:pk>/", ListingDetailView.as_view(), name="detail"),
    path("<int:listing_id>/images/", ListingImageUploadView.as_view(), name="upload-image"),
]
