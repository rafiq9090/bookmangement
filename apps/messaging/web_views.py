from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from apps.listings.models import BookListing
from apps.messaging.models import Conversation, InquiryMessage
from apps.orders.models import Cart, CartItem
from apps.orders.services.cart import get_cart_items_for_request


@login_required(login_url="/login/")
def inbox_view(request):
    """
    Shows buyer inquiries and seller messages in a unified message inbox.
    """
    user = request.user
    conversations = (
        Conversation.objects.filter(Q(buyer=user) | Q(seller=user))
        .select_related("listing__book", "listing__seller__seller_profile", "buyer", "seller")
        .prefetch_related("messages", "listing__images")
        .order_by("-updated_at")
    )

    buyer_threads = []
    seller_threads = []

    for conv in conversations:
        conv.last_msg = conv.messages.last()
        conv.unread_count = conv.messages.exclude(sender=user).filter(is_read=False).count()
        if conv.seller == user:
            seller_threads.append(conv)
        else:
            buyer_threads.append(conv)

    _, _, cart_count = get_cart_items_for_request(request)

    return render(
        request,
        "messaging/inbox.html",
        {
            "buyer_threads": buyer_threads,
            "seller_threads": seller_threads,
            "cart_count": cart_count,
            "active_tab": request.GET.get("tab", "seller" if user.is_seller and seller_threads else "buyer"),
        },
    )


@login_required(login_url="/login/")
def start_inquiry_view(request, listing_id):
    """
    Entry point when buyer clicks 'Contact Seller to Order' from a book listing page.
    Creates or resumes conversation thread and sends initial inquiry request.
    """
    listing = get_object_or_404(
        BookListing.objects.select_related("seller", "book"),
        id=listing_id,
        status=BookListing.Status.ACTIVE,
        is_deleted=False,
    )

    if listing.seller == request.user:
        messages.warning(request, "You cannot purchase or inquire about your own book listing.")
        return redirect("book_detail", slug=listing.book.slug)

    conversation, created = Conversation.objects.get_or_create(
        listing=listing,
        buyer=request.user,
        seller=listing.seller,
    )

    custom_message = request.POST.get("message", "").strip() if request.method == "POST" else ""

    if created or custom_message:
        text = custom_message or (
            f"Hello! I am interested in purchasing '{listing.book.title}' "
            f"({listing.get_condition_display()}, ৳{listing.price}). "
            "Please confirm if the book is available so I can proceed with the purchase."
        )
        InquiryMessage.objects.create(
            conversation=conversation,
            sender=request.user,
            text=text,
        )
        messages.success(request, "Inquiry sent to seller! You will be able to complete purchase once the seller confirms.")

    return redirect("conversation_detail", conversation_id=conversation.id)


@login_required(login_url="/login/")
def conversation_detail_view(request, conversation_id):
    """
    Dedicated chat thread between buyer and seller for a listing.
    Features:
    - Real-time message exchange
    - Seller 'Confirm Order' / 'Decline' actions
    - Buyer 'Proceed to Checkout' button once confirmed
    """
    conversation = get_object_or_404(
        Conversation.objects.select_related(
            "listing__book",
            "listing__seller__seller_profile",
            "buyer",
            "seller",
        ).prefetch_related("listing__images"),
        id=conversation_id,
    )

    user = request.user
    if user != conversation.buyer and user != conversation.seller:
        raise Http404("You do not have permission to view this conversation.")

    # Mark incoming messages as read
    conversation.messages.exclude(sender=user).filter(is_read=False).update(is_read=True)

    is_seller = (user == conversation.seller)
    is_buyer = (user == conversation.buyer)

    if request.method == "POST":
        action = request.POST.get("action", "send_message")

        if action == "confirm_order":
            if not is_seller:
                messages.error(request, "Only the seller can confirm this order.")
                return redirect("conversation_detail", conversation_id=conversation.id)

            conversation.order_status = Conversation.OrderStatus.CONFIRMED
            conversation.confirmed_price = conversation.listing.price
            conversation.confirmed_at = timezone.now()
            conversation.save()

            InquiryMessage.objects.create(
                conversation=conversation,
                sender=user,
                text=f"✅ Order Confirmed! I have approved your order request for ৳{conversation.listing.price}. You can now click 'Purchase Now' to proceed with your payment.",
            )
            messages.success(request, "You have approved and confirmed this order! The buyer can now purchase.")
            return redirect("conversation_detail", conversation_id=conversation.id)

        elif action == "decline_order":
            if not is_seller:
                messages.error(request, "Only the seller can decline this order.")
                return redirect("conversation_detail", conversation_id=conversation.id)

            conversation.order_status = Conversation.OrderStatus.DECLINED
            conversation.save()

            InquiryMessage.objects.create(
                conversation=conversation,
                sender=user,
                text="❌ Order request declined. The book is currently unavailable or cannot be fulfilled.",
            )
            messages.info(request, "Order request marked as declined.")
            return redirect("conversation_detail", conversation_id=conversation.id)

        elif action == "send_message":
            text = request.POST.get("text", "").strip()
            photo = request.FILES.get("photo_evidence")

            if text or photo:
                InquiryMessage.objects.create(
                    conversation=conversation,
                    sender=user,
                    text=text or "Attached photo",
                    photo_evidence=photo,
                )
                conversation.updated_at = timezone.now()
                conversation.save(update_fields=["updated_at"])

            return redirect("conversation_detail", conversation_id=conversation.id)

    chat_messages = conversation.messages.select_related("sender").order_by("created_at")
    _, _, cart_count = get_cart_items_for_request(request)

    return render(
        request,
        "messaging/conversation_detail.html",
        {
            "conversation": conversation,
            "listing": conversation.listing,
            "chat_messages": chat_messages,
            "is_seller": is_seller,
            "is_buyer": is_buyer,
            "cart_count": cart_count,
        },
    )


@login_required(login_url="/login/")
def proceed_to_checkout_from_chat(request, conversation_id):
    """
    Unlocked once seller confirms the order. Buyer clicks 'Purchase Now' ->
    adds listing to cart and forwards directly to checkout.
    """
    conversation = get_object_or_404(
        Conversation.objects.select_related("listing"),
        id=conversation_id,
        buyer=request.user,
    )

    if conversation.order_status != Conversation.OrderStatus.CONFIRMED:
        messages.warning(request, "Please wait for the seller to confirm the order before purchasing.")
        return redirect("conversation_detail", conversation_id=conversation.id)

    # Ensure listing is in buyer's cart
    cart, _ = Cart.objects.get_or_create(user=request.user)
    existing_item = CartItem.objects.filter(listing=conversation.listing).first()
    if existing_item:
        if existing_item.cart_id != cart.id:
            existing_item.cart = cart
            existing_item.save(update_fields=["cart"])
    else:
        CartItem.objects.create(cart=cart, listing=conversation.listing)

    messages.success(request, f"Order confirmed by seller! Proceed to checkout for '{conversation.listing.book.title}'.")
    return redirect("checkout")
