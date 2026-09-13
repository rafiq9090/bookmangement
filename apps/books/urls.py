from django.urls import path
from apps.books.views import BookDetailView, BookListView, BookLookupByIsbnView, CategoryListView

app_name = "books"

urlpatterns = [
    path("", BookListView.as_view(), name="list"),
    path("lookup-isbn/", BookLookupByIsbnView.as_view(), name="lookup-isbn"),
    path("categories/", CategoryListView.as_view(), name="category-list"),
    path("<slug:slug>/", BookDetailView.as_view(), name="detail"),
]
