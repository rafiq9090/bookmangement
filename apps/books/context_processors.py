from django.db.models import Count
from apps.books.models import Category
from apps.orders.services.cart import get_cart_items_for_request


def global_marketplace_context(request):
    """
    Global Context Processor for the Bookstore Marketplace.
    Injects dynamic categories and real-time cart count into every template.
    """
    try:
        nav_categories = Category.objects.annotate(book_count=Count("books")).order_by("-book_count")
    except Exception:
        nav_categories = []

    try:
        _, _, cart_count = get_cart_items_for_request(request)
    except Exception:
        cart_count = 0

    return {
        "nav_categories": nav_categories,
        "global_cart_count": cart_count,
    }
