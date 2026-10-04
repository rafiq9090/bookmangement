from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.core.paginator import Paginator
from django.http import Http404, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from apps.listings.models import BookListing
from apps.messaging.models import Conversation, InquiryMessage
from apps.orders.models import Cart, CartItem
from apps.orders.services.cart import get_cart_items_for_request


def clean_api_exception(exc):
    detail = getattr(exc, 'detail', str(exc))
    if isinstance(detail, (list, tuple)):
        return " ".join(str(d) for d in detail)
    elif isinstance(detail, dict):
        parts = []
        for k, v in detail.items():
            val_str = " ".join(str(i) for i in v) if isinstance(v, (list, tuple)) else str(v)
            parts.append(f"{k.replace('_', ' ').capitalize()}: {val_str}")
        return " ".join(parts)
    return str(detail)



@login_required(login_url="/login/")
def inbox_view(request):
    """
    Messenger-style unified inbox: all conversations in one left sidebar,
    chat opens in the right panel when clicked.
    """
    user = request.user
    conversations = (
        Conversation.objects.filter(Q(buyer=user) | Q(seller=user))
        .select_related("listing__book", "listing__seller__seller_profile", "buyer", "seller")
        .order_by("-updated_at")
    )

    thread_page = Paginator(conversations, 50).get_page(request.GET.get("page"))
    all_threads = []
    for conv in thread_page:
        conv.last_msg = conv.messages.last()
        conv.unread_count = conv.messages.exclude(sender=user).filter(is_read=False).count()
        conv.is_seller_role = (conv.seller == user)
        conv.other_user = conv.buyer if conv.is_seller_role else conv.seller
        conv.display_name = conv.other_user.get_full_name() or "Reader"
        if not conv.is_seller_role:
            profile = getattr(conv.seller, 'seller_profile', None)
            if profile:
                conv.display_name = profile.store_name
        conv.initials = ''.join(part[0] for part in conv.display_name.split()[:2]).upper()
        all_threads.append(conv)

    # Pre-load the first conversation's messages if there are threads
    active_conv = None
    active_chat_messages = None
    active_is_seller = False
    active_is_buyer = False
    active_pickup = None
    selected_id = request.GET.get("conv")
    if selected_id:
        for t in all_threads:
            if str(t.id) == selected_id:
                active_conv = t
                break
    if active_conv is None and selected_id and selected_id.isdigit():
        active_conv = get_object_or_404(conversations, pk=int(selected_id))
        active_conv.other_user = active_conv.buyer if active_conv.seller_id == user.pk else active_conv.seller
        active_conv.display_name = active_conv.other_user.get_full_name() or "Reader"
        if active_conv.buyer_id == user.pk:
            profile = getattr(active_conv.seller, 'seller_profile', None)
            if profile:
                active_conv.display_name = profile.store_name
        active_conv.initials = ''.join(part[0] for part in active_conv.display_name.split()[:2]).upper()
    if active_conv is None and all_threads:
        active_conv = all_threads[0]

    if active_conv:
        # Mark as read
        active_conv.messages.exclude(sender=user).filter(is_read=False).update(is_read=True)
        active_is_seller = (active_conv.seller == user)
        active_is_buyer = (active_conv.buyer == user)
        history = active_conv.messages.select_related("sender").order_by("-id")
        before_id = request.GET.get("before_id", "")
        if before_id.isdigit():
            history = history.filter(id__lt=int(before_id))
        active_chat_messages = list(reversed(history[:200]))
        active_conv.unread_count = 0
        active_pickup = active_conv.agreements.order_by("-created_at").first()

    _, _, cart_count = get_cart_items_for_request(request)

    return render(
        request,
        "messaging/inbox.html",
        {
            "all_threads": all_threads,
            "page_obj": thread_page,
            "last_message_id": active_conv.messages.order_by("-id").values_list("id", flat=True).first() if active_conv else 0,
            "history_previous_id": active_chat_messages[0].pk if active_chat_messages and len(active_chat_messages) == 200 else 0,
            "viewing_history": bool(request.GET.get("before_id")),
            "active_conv": active_conv,
            "active_chat_messages": active_chat_messages,
            "active_is_seller": active_is_seller,
            "active_is_buyer": active_is_buyer,
            "active_pickup": active_pickup,
            "cart_count": cart_count,
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

        if action in ("confirm_order", "decline_order"):
            from apps.orders.models import PurchaseAgreement
            from apps.orders.services.pickup import create_purchase_request, act_on_agreement
            from rest_framework.exceptions import APIException
            try:
                if not is_seller:
                    from rest_framework.exceptions import PermissionDenied
                    raise PermissionDenied("Only the seller can accept or decline.")
                agreement = PurchaseAgreement.objects.filter(conversation=conversation).order_by("-created_at").first()
                if agreement is None:
                    agreement = create_purchase_request(conversation.buyer, conversation.listing_id)
                act_on_agreement(agreement.pk, user, "accept" if action == "confirm_order" else "decline")
                return redirect("pickup_detail", pk=agreement.pk)
            except APIException as exc:
                messages.error(request, clean_api_exception(exc))
                return redirect("conversation_detail", conversation_id=conversation.id)

        elif action == "send_message":
            text = request.POST.get("text", "").strip()
            photo = request.FILES.get("photo_evidence")
            if len(text) > 5000:
                messages.error(request, "Messages must be at most 5000 characters.")
                return redirect("conversation_detail", conversation_id=conversation.pk)

            if text or photo:
                InquiryMessage.objects.create(
                    conversation=conversation,
                    sender=user,
                    text=text or "Attached photo",
                    photo_evidence=photo,
                )
                from apps.orders.services.pickup import notify
                notify(conversation, user, "New message about " + conversation.listing.book.title[:180])
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
            "pickup_agreement": conversation.agreements.order_by("-created_at").first(),
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

    from apps.orders.models import PurchaseAgreement
    from apps.orders.services.pickup import create_purchase_request
    from rest_framework.exceptions import APIException
    agreement = PurchaseAgreement.objects.filter(conversation=conversation).order_by("-created_at").first()
    if agreement:
        return redirect("pickup_detail", pk=agreement.pk)
    if request.method != "POST":
        return redirect("conversation_detail", conversation_id=conversation.pk)
    try:
        agreement = create_purchase_request(request.user, conversation.listing_id)
        return redirect("pickup_detail", pk=agreement.pk)
    except APIException as exc:
        messages.error(request, clean_api_exception(exc))
        return redirect("conversation_detail", conversation_id=conversation.pk)


@login_required(login_url="/login/")
def inbox_unread_count_api(request):
    """
    Lightweight endpoint returning live unread message count across all conversations.
    Enables header badges to update in real time without full page reloads.
    """
    user = request.user
    unread_count = (
        InquiryMessage.objects.filter(
            Q(conversation__buyer=user) | Q(conversation__seller=user)
        )
        .exclude(sender=user)
        .filter(is_read=False)
        .count()
    )
    latest_msg = (
        InquiryMessage.objects.filter(
            Q(conversation__buyer=user) | Q(conversation__seller=user)
        )
        .exclude(sender=user)
        .order_by("-created_at")
        .first()
    )
    return JsonResponse({
        "unread_count": unread_count,
        "latest_id": latest_msg.id if latest_msg else 0,
    })


@login_required(login_url="/login/")
def inbox_threads_api(request):
    """
    Returns thread summary for inbox view to update unread counters and previews in real time.
    """
    user = request.user
    conversations = (
        Conversation.objects.filter(Q(buyer=user) | Q(seller=user))
        .select_related("listing__book", "listing__seller__seller_profile", "buyer", "seller")
        .order_by("-updated_at")
    )
    conversations = Paginator(conversations, 50).get_page(request.GET.get("page"))
    threads = []
    unread_total = InquiryMessage.objects.filter(Q(conversation__buyer=user) | Q(conversation__seller=user)).exclude(sender=user).filter(is_read=False).count()
    for conv in conversations:
        last = conv.messages.last()
        unread = conv.messages.exclude(sender=user).filter(is_read=False).count()
        threads.append({
            "id": conv.id,
            "is_seller": (conv.seller_id == user.id),
            "unread_count": unread,
            "last_message": last.text if last else "",
            "last_time": last.created_at.strftime("%I:%M %p") if last else "",
            "updated_at": conv.updated_at.isoformat(),
        })
    return JsonResponse({
        "unread_count": unread_total,
        "threads": threads,
    })


@login_required(login_url="/login/")
def conversation_messages_api(request, conversation_id):
    """
    Returns new messages in a conversation for live real-time chat updates without reloading.
    Also handles POST to send messages asynchronously via AJAX.
    """
    conversation = get_object_or_404(
        Conversation.objects.select_related("buyer", "seller", "listing__book"),
        id=conversation_id,
    )
    user = request.user
    if user != conversation.buyer and user != conversation.seller:
        return JsonResponse({"error": "Forbidden"}, status=403)

    if request.method == "POST":
        text = request.POST.get("text", "").strip()
        photo = request.FILES.get("photo_evidence")
        if len(text) > 5000:
            return JsonResponse({"error": "Messages must be at most 5000 characters."}, status=400)
        if text or photo:
            msg = InquiryMessage.objects.create(
                conversation=conversation,
                sender=user,
                text=text or "Attached photo",
                photo_evidence=photo,
            )
            from apps.orders.services.pickup import notify
            notify(conversation, user, "New message about " + conversation.listing.book.title[:180])
            conversation.updated_at = timezone.now()
            conversation.save(update_fields=["updated_at"])
            return JsonResponse({
                "success": True,
                "message": {
                    "id": msg.id,
                    "sender_id": msg.sender_id,
                    "sender_name": msg.sender.get_full_name() or "Reader",
                    "sender_initial": (msg.sender.first_name or msg.sender.email)[:1].upper(),
                    "is_me": True,
                    "text": msg.text,
                    "photo_url": msg.photo_evidence.url if msg.photo_evidence else "",
                    "created_at_time": timezone.localtime(msg.created_at).strftime("%I:%M %p"),
                },
            })
        return JsonResponse({"error": "Empty message"}, status=400)

    after_id = request.GET.get("after_id")
    qs = conversation.messages.select_related("sender").order_by("created_at")
    if after_id and after_id.isdigit():
        qs = qs.filter(id__gt=int(after_id))

    incoming = qs.exclude(sender=user).filter(is_read=False)
    if incoming.exists():
        incoming.update(is_read=True)

    messages_data = [
        {
            "id": m.id,
            "sender_id": m.sender_id,
            "sender_name": m.sender.get_full_name() or "Reader",
            "sender_initial": (m.sender.first_name or m.sender.email)[:1].upper(),
            "is_me": (m.sender_id == user.id),
            "text": m.text,
            "photo_url": m.photo_evidence.url if m.photo_evidence else "",
            "created_at_time": timezone.localtime(m.created_at).strftime("%I:%M %p"),
        }
        for m in qs[:200]
    ]

    unread_total = (
        InquiryMessage.objects.filter(
            Q(conversation__buyer=user) | Q(conversation__seller=user)
        )
        .exclude(sender=user)
        .filter(is_read=False)
        .count()
    )

    return JsonResponse({
        "messages": messages_data,
        "unread_count": unread_total,
    })
