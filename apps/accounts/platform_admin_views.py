from decimal import Decimal
import uuid
from config.security import safe_next
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

    next_url = safe_next(request, "/admin/dashboard/")

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
    from apps.accounts.marketplace_admin import dashboard
    return dashboard(request)
