from decimal import Decimal
import uuid
from django.contrib import messages
from django.contrib.auth import authenticate, login
from django.contrib.admin.views.decorators import staff_member_required
from django.db import transaction
from django.db.models import Count, Q, Sum
from django.shortcuts import get_object_or_404, redirect, render

from apps.accounts.models import CustomUser, SellerProfile
from apps.listings.models import BookListing
from apps.orders.models import Order, OrderShipment
from apps.orders.services.cart import get_cart_items_for_request
from apps.payments.models import EscrowHold, PayoutBatch, SellerLedger


def platform_admin_login_view(request):
    """
    Dedicated Platform Admin Login Page (/admin-login/)
    Staff/Superuser credentials required.
    """
    if request.user.is_authenticated and (request.user.is_staff or request.user.is_superuser):
        return redirect("/admin/dashboard/")

    next_url = request.GET.get("next") or request.POST.get("next") or "/admin/dashboard/"

    if request.method == "POST":
        email = request.POST.get("email", "").strip().lower()
        password = request.POST.get("password", "")

        if not email or not password:
            messages.error(request, "Please enter both administrative email and password.")
            return render(request, "admin/admin_login.html", {"email": email, "next": next_url})

        user = authenticate(request, username=email, password=password)
        if user is None:
            messages.error(request, "Invalid administrative email or password.")
            return render(request, "admin/admin_login.html", {"email": email, "next": next_url})

        if not (user.is_staff or user.is_superuser):
            messages.error(
                request,
                "Access Denied: This account is not registered as a platform administrator. Standard users should sign in through the main website."
            )
            return render(request, "admin/admin_login.html", {"email": email, "next": next_url})

        login(request, user)
        messages.success(request, f"Welcome back, {user.first_name or user.email}! Admin session verified.")
        return redirect(next_url)

    return render(request, "admin/admin_login.html", {"next": next_url})


def platform_admin_dashboard_view(request):
    """
    Dedicated Modern Marketplace Platform Admin Dashboard (/admin/dashboard/)
    Restricted to Staff and Superuser administrators.
    Manages:
      1. Platform Revenue & Financial KPIs (GMV, 15% Platform Fees, Escrow Custody, Payouts)
      2. Seller KYC Verification Queue (Approve / Reject)
      3. Escrow Custody & Seller Payout Batches (bKash / Nagad / Bank)
      4. Global Orders & Courier Dispatch Monitor (Steadfast, Pathao)
      5. Marketplace Catalog & Listings Moderation
    """
    if not request.user.is_authenticated or not (request.user.is_staff or request.user.is_superuser):
        messages.error(request, "Administrative access restricted. Please sign in with an authorized staff account.")
        return redirect(f"/admin-login/?next=/admin/dashboard/")

    active_tab = request.GET.get("tab", "overview").lower()
    if active_tab not in ["overview", "kyc", "payouts", "orders", "listings"]:
        active_tab = "overview"

    # ==================== HANDLE ADMINISTRATIVE POST ACTIONS ====================
    if request.method == "POST":
        action = request.POST.get("action")

        # 1. Approve Seller KYC
        if action == "approve_kyc":
            profile_id = request.POST.get("profile_id")
            profile = get_object_or_404(SellerProfile, id=profile_id)
            with transaction.atomic():
                profile.kyc_status = SellerProfile.KycStatus.VERIFIED
                profile.save(update_fields=["kyc_status"])
                profile.user.is_seller = True
                profile.user.save(update_fields=["is_seller"])
            messages.success(request, f"Seller '{profile.store_name}' ({profile.user.email}) has been APPROVED and verified!")
            return redirect("/admin/dashboard/?tab=kyc")

        # 2. Reject Seller KYC
        elif action == "reject_kyc":
            profile_id = request.POST.get("profile_id")
            profile = get_object_or_404(SellerProfile, id=profile_id)
            profile.kyc_status = SellerProfile.KycStatus.REJECTED
            profile.save(update_fields=["kyc_status"])
            messages.warning(request, f"Seller '{profile.store_name}' KYC application was marked REJECTED.")
            return redirect("/admin/dashboard/?tab=kyc")

        # 3. Complete Payout Batch
        elif action == "complete_payout":
            batch_id = request.POST.get("batch_id")
            payout = get_object_or_404(PayoutBatch, id=batch_id)
            payout.status = PayoutBatch.Status.COMPLETED
            payout.save(update_fields=["status"])
            messages.success(request, f"Payout of ${payout.amount} via {payout.payout_method} to {payout.seller.email} marked as COMPLETED.")
            return redirect("/admin/dashboard/?tab=payouts")

        # 4. Release Escrow Hold to Seller
        elif action == "release_escrow":
            escrow_id = request.POST.get("escrow_id")
            escrow = get_object_or_404(EscrowHold, id=escrow_id)
            escrow.status = EscrowHold.EscrowStatus.RELEASED
            escrow.save(update_fields=["status"])
            messages.success(request, f"Escrow Hold #${str(escrow.id)[:8]} (${escrow.seller_net_amount}) released to {escrow.shipment.seller.email}.")
            return redirect("/admin/dashboard/?tab=payouts")

        # 5. Moderate Book Listing (Toggle Status / Delete)
        elif action == "toggle_listing":
            listing_id = request.POST.get("listing_id")
            listing = get_object_or_404(BookListing, id=listing_id)
            if listing.status == BookListing.Status.ACTIVE:
                listing.status = BookListing.Status.ARCHIVED
                messages.info(request, f"Listing '{listing.book.title}' archived.")
            else:
                listing.status = BookListing.Status.ACTIVE
                messages.success(request, f"Listing '{listing.book.title}' activated.")
            listing.save(update_fields=["status", "updated_at"])
            return redirect("/admin/dashboard/?tab=listings")

    # ==================== PLATFORM FINANCIAL KPIS ====================
    # 1. Gross Merchandise Value (GMV)
    gmv_agg = Order.objects.filter(status__in=[Order.Status.PAID, Order.Status.COMPLETED]).aggregate(total=Sum("total_amount"))
    total_gmv = gmv_agg["total"] or Decimal("0.00")

    # 2. Platform Commission Revenue (15% Commission Collected)
    commission_agg = SellerLedger.objects.filter(entry_type=SellerLedger.EntryType.PLATFORM_FEE).aggregate(total=Sum("amount"))
    platform_revenue = commission_agg["total"] or Decimal("0.00")

    # 3. Escrow In Custody (Pending Delivery & Return window)
    escrow_agg = EscrowHold.objects.filter(status=EscrowHold.EscrowStatus.HELD).aggregate(total=Sum("gross_amount"))
    escrow_held = escrow_agg["total"] or Decimal("0.00")

    # 4. Completed Payouts to Sellers
    payout_agg = PayoutBatch.objects.filter(status=PayoutBatch.Status.COMPLETED).aggregate(total=Sum("amount"))
    total_payouts = payout_agg["total"] or Decimal("0.00")

    # Pending Action Counters
    pending_kyc_count = SellerProfile.objects.filter(kyc_status=SellerProfile.KycStatus.PENDING).count()
    pending_payout_count = PayoutBatch.objects.filter(status=PayoutBatch.Status.REQUESTED).count()
    pending_dispatch_count = OrderShipment.objects.filter(status=OrderShipment.ShipmentStatus.WAITING_SELLER).count()
    total_users_count = CustomUser.objects.count()
    total_sellers_count = CustomUser.objects.filter(is_seller=True).count()
    total_orders_count = Order.objects.count()
    total_listings_count = BookListing.objects.filter(is_deleted=False).count()

    # ==================== TAB-SPECIFIC DATASETS ====================
    # 1. KYC Tab Data
    kyc_filter = request.GET.get("kyc_status", "ALL").upper()
    sellers_query = SellerProfile.objects.select_related("user").order_by("-created_at")
    if kyc_filter != "ALL":
        sellers_query = sellers_query.filter(kyc_status=kyc_filter)

    # 2. Payouts Tab Data
    payout_batches = PayoutBatch.objects.select_related("seller").order_by("-created_at")[:40]
    escrow_holds = EscrowHold.objects.select_related("order", "shipment__seller").order_by("-created_at")[:40]

    # 3. Orders Tab Data
    orders_status = request.GET.get("order_status", "ALL").upper()
    all_orders = Order.objects.select_related("buyer").prefetch_related("shipments__seller", "shipments__items__listing__book").order_by("-created_at")
    if orders_status != "ALL":
        all_orders = all_orders.filter(status=orders_status)

    # 4. Listings Tab Data
    listing_search = request.GET.get("q", "").strip()
    listing_status = request.GET.get("listing_status", "ALL").upper()
    marketplace_listings = BookListing.objects.filter(is_deleted=False).select_related("book", "seller").prefetch_related("images").order_by("-created_at")
    if listing_status != "ALL":
        marketplace_listings = marketplace_listings.filter(status=listing_status)
    if listing_search:
        marketplace_listings = marketplace_listings.filter(
            Q(book__title__icontains=listing_search) |
            Q(book__isbn_13__icontains=listing_search) |
            Q(seller__email__icontains=listing_search)
        )

    # 5. Overview Recent Streams
    recent_orders = all_orders[:8]
    recent_sellers = SellerProfile.objects.select_related("user").filter(kyc_status=SellerProfile.KycStatus.PENDING)[:5]
    recent_payouts = payout_batches[:5]

    _, _, cart_count = get_cart_items_for_request(request)

    return render(
        request,
        "admin/platform_dashboard.html",
        {
            "active_tab": active_tab,
            # Financial KPIs
            "total_gmv": total_gmv,
            "platform_revenue": platform_revenue,
            "escrow_held": escrow_held,
            "total_payouts": total_payouts,
            # Metrics Counters
            "pending_kyc_count": pending_kyc_count,
            "pending_payout_count": pending_payout_count,
            "pending_dispatch_count": pending_dispatch_count,
            "total_users_count": total_users_count,
            "total_sellers_count": total_sellers_count,
            "total_orders_count": total_orders_count,
            "total_listings_count": total_listings_count,
            # Tab 1: Overview
            "recent_orders": recent_orders,
            "recent_sellers": recent_sellers,
            "recent_payouts": recent_payouts,
            # Tab 2: KYC
            "sellers_query": sellers_query,
            "kyc_filter": kyc_filter,
            # Tab 3: Payouts & Escrow
            "payout_batches": payout_batches,
            "escrow_holds": escrow_holds,
            # Tab 4: Orders & Shipments
            "all_orders": all_orders[:50],
            "orders_status": orders_status,
            # Tab 5: Catalog Listings
            "marketplace_listings": marketplace_listings[:60],
            "listing_status": listing_status,
            "listing_search": listing_search,
            "cart_count": cart_count,
        },
    )
