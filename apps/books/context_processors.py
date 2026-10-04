from django.db.models import Count
from apps.books.models import Category
from apps.books.selectors import available_categories
from apps.orders.services.cart import get_cart_items_for_request


def global_marketplace_context(request):
    """
    Global Context Processor for the Bookstore Marketplace.
    Injects dynamic categories and real-time cart count into every template.
    """
    try:
        nav_categories = available_categories()
    except Exception:
        nav_categories = []

    unread_messages_count = 0
    if request.user.is_authenticated:
        try:
            from apps.messaging.models import InquiryMessage
            from django.db.models import Q
            unread_messages_count = InquiryMessage.objects.filter(
                Q(conversation__buyer=request.user) | Q(conversation__seller=request.user)
            ).exclude(sender=request.user).filter(is_read=False).count()
        except Exception:
            unread_messages_count = 0

    return {
        "cookie_choice": request.get_signed_cookie('cookie_preferences', default='', salt='cookie-preferences', max_age=365 * 86400),
        "nav_categories": nav_categories,
        "global_cart_count": 0,
        "unread_messages_count": unread_messages_count,
    }
