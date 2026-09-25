from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.shortcuts import get_object_or_404, redirect, render

from apps.accounts.models import Address, CustomUser, SellerProfile
from apps.accounts.services.users import apply_for_seller_account
from apps.orders.models import Order
from apps.orders.services.cart import get_cart_items_for_request, migrate_session_cart_to_user


def login_register_view(request):
    """
    Page 11: Login & Register Page (/login/ & /register/)
    Supports dual-mode tab switching, buyer/seller account creation, session auth, and cart migration.
    """
    mode = request.GET.get("mode", "login").lower()
    if request.path.rstrip("/") == "/register":
        mode = "register"
    
    next_url = request.GET.get("next") or request.POST.get("next") or "profile"
    _, _, cart_count = get_cart_items_for_request(request)

    if request.method == "POST":
        action = request.POST.get("action", "login")

        if action == "login":
            email = request.POST.get("email", "").strip().lower()
            password = request.POST.get("password", "")

            user = authenticate(request, username=email, password=password)
            if user is not None:
                login(request, user)
                migrate_session_cart_to_user(request, user)
                messages.success(request, f"Welcome back, {user.first_name or user.email}!")
                return redirect(next_url)
            else:
                messages.error(request, "Invalid email or password. Please try again.")
                mode = "login"

        elif action == "register":
            first_name = request.POST.get("first_name", "").strip()
            last_name = request.POST.get("last_name", "").strip()
            email = request.POST.get("email", "").strip().lower()
            phone_number = request.POST.get("phone_number", "").strip()
            password = request.POST.get("password", "")
            confirm_password = request.POST.get("confirm_password", "")
            account_type = request.POST.get("account_type", "buyer")
            store_name = request.POST.get("store_name", "").strip()
            is_seller = (account_type == "seller" or bool(request.POST.get("become_seller")))

            if not email or not password:
                messages.error(request, "Email and password are required.")
                mode = "register"
            elif password != confirm_password:
                messages.error(request, "Passwords do not match.")
                mode = "register"
            elif len(password) < 6:
                messages.error(request, "Password must be at least 6 characters.")
                mode = "register"
            elif CustomUser.objects.filter(email=email).exists():
                messages.error(request, "An account with this email already exists. Please log in.")
                mode = "login"
            else:
                user = CustomUser.objects.create_user(
                    email=email,
                    password=password,
                    first_name=first_name,
                    last_name=last_name,
                    phone_number=phone_number,
                    is_seller=is_seller,
                )
                if "avatar" in request.FILES:
                    user.avatar = request.FILES["avatar"]
                    user.save(update_fields=["avatar"])

                login(request, user)
                migrate_session_cart_to_user(request, user)

                if is_seller:
                    if store_name:
                        SellerProfile.objects.get_or_create(
                            user=user,
                            defaults={
                                "store_name": store_name,
                                "kyc_status": SellerProfile.KycStatus.PENDING,
                            },
                        )
                    messages.success(request, f"Welcome, {user.first_name or 'Seller'}! Your seller account is active. Complete your store profile below.")
                    return redirect("seller_apply")
                else:
                    messages.success(request, f"Welcome to e-Book, {user.first_name or 'Friend'}! Your buyer account is ready.")
                    return redirect(next_url)

    return render(
        request,
        "accounts/login_register.html",
        {
            "mode": mode,
            "next": next_url,
            "cart_count": cart_count,
        },
    )


def logout_view(request):
    """
    Terminates user session and redirects to home.
    """
    logout(request)
    messages.info(request, "You have been successfully logged out.")
    return redirect("home")


def user_profile_view(request):
    """
    Page 12: User Profile & Addresses (/profile/)
    Displays user info, addresses, recent orders, and security options.
    """
    if request.user.is_authenticated:
        user = request.user
    else:
        user = CustomUser.objects.first()
        if not user:
            user = CustomUser.objects.create_user(
                email="customer@edoxbookshop.com",
                password="DemoPassword123!",
                first_name="Leslie",
                last_name="Alexander",
            )

    active_tab = request.GET.get("tab", "info")
    _, _, cart_count = get_cart_items_for_request(request)

    # Handle Profile Update POST
    if request.method == "POST":
        form_type = request.POST.get("form_type")

        if form_type == "update_info":
            first_name = request.POST.get("first_name", "").strip()
            last_name = request.POST.get("last_name", "").strip()
            phone_number = request.POST.get("phone_number", "").strip()
            
            user.first_name = first_name
            user.last_name = last_name
            user.phone_number = phone_number

            if "avatar" in request.FILES:
                user.avatar = request.FILES["avatar"]

            user.save()
            messages.success(request, "Your profile information has been updated.")
            return redirect("profile")

        elif form_type == "update_avatar":
            if "avatar" in request.FILES:
                user.avatar = request.FILES["avatar"]
                user.save(update_fields=["avatar"])
                messages.success(request, "Profile photo uploaded and saved successfully!")
            else:
                messages.error(request, "Please select an image file to upload.")
            return redirect("profile")

        elif form_type == "add_address":
            recipient_name = request.POST.get("recipient_name", "").strip()
            phone_number = request.POST.get("phone_number", "").strip()
            street_address = request.POST.get("street_address", "").strip()
            city = request.POST.get("city", "").strip()
            state_division = request.POST.get("state_division", "").strip()
            postal_code = request.POST.get("postal_code", "").strip()
            is_default = bool(request.POST.get("is_default"))

            if recipient_name and street_address and city:
                Address.objects.create(
                    user=user,
                    recipient_name=recipient_name,
                    phone_number=phone_number,
                    street_address=street_address,
                    city=city,
                    state_division=state_division,
                    postal_code=postal_code,
                    is_default=is_default,
                )
                messages.success(request, "Delivery address added successfully.")
            active_tab = "addresses"
            return redirect(f"/profile/?tab=addresses")

        elif form_type == "change_password":
            current_password = request.POST.get("current_password", "")
            new_password = request.POST.get("new_password", "")
            confirm_new_password = request.POST.get("confirm_new_password", "")

            if not user.check_password(current_password):
                messages.error(request, "Your current password is incorrect.")
            elif new_password != confirm_new_password:
                messages.error(request, "New passwords do not match.")
            elif len(new_password) < 6:
                messages.error(request, "Password must be at least 6 characters.")
            else:
                user.set_password(new_password)
                user.save()
                if request.user.is_authenticated:
                    login(request, user)
                messages.success(request, "Your password has been changed successfully.")
            active_tab = "security"
            return redirect(f"/profile/?tab=security")

    addresses = Address.objects.filter(user=user)
    if not addresses.exists():
        Address.objects.create(
            user=user,
            recipient_name=f"{user.first_name} {user.last_name}".strip() or "Leslie Alexander",
            phone_number=user.phone_number or "+880 1712 345678",
            street_address="House 42, Road 11, Banani",
            city="Dhaka",
            state_division="Dhaka Division",
            postal_code="1213",
            is_default=True,
        )
        addresses = Address.objects.filter(user=user)

    orders = Order.objects.filter(buyer=user).prefetch_related("shipments__items__listing__book").order_by("-created_at")[:10]
    seller_profile = getattr(user, "seller_profile", None)

    return render(
        request,
        "accounts/profile.html",
        {
            "profile_user": user,
            "active_tab": active_tab,
            "addresses": addresses,
            "orders": orders,
            "seller_profile": seller_profile,
            "cart_count": cart_count,
        },
    )


def address_action_view(request, id, action):
    """
    Sets default or deletes an address.
    """
    if request.user.is_authenticated:
        user = request.user
    else:
        user = CustomUser.objects.first()

    address = get_object_or_404(Address, id=id, user=user)

    if action == "set_default":
        address.is_default = True
        address.save()
        messages.success(request, f"'{address.street_address}' set as default address.")
    elif action == "delete":
        address.delete()
        messages.success(request, "Address removed.")

    return redirect("/profile/?tab=addresses")


def seller_apply_view(request):
    """
    Page 13: Become a Seller Application (/seller/apply/)
    Onboarding landing page with perks and application form for verified sellers.
    """
    if request.user.is_authenticated:
        user = request.user
    else:
        user = CustomUser.objects.filter(is_seller=False).first() or CustomUser.objects.first()

    _, _, cart_count = get_cart_items_for_request(request)
    existing_profile = getattr(user, "seller_profile", None)

    if request.method == "POST":
        store_name = request.POST.get("store_name", "").strip()
        bio = request.POST.get("bio", "").strip()
        national_id_number = request.POST.get("national_id_number", "").strip()
        payout_method = request.POST.get("payout_method", "BKASH").upper()
        payout_account_details = request.POST.get("payout_account_details", "").strip()

        if not store_name or not payout_account_details:
            messages.error(request, "Please enter your Store Name and Payout Account details.")
        elif SellerProfile.objects.filter(store_name__iexact=store_name).exclude(user=user).exists():
            messages.error(request, f"The store name '{store_name}' is already taken. Please choose another.")
        else:
            if existing_profile:
                existing_profile.store_name = store_name
                existing_profile.bio = bio
                existing_profile.national_id_number = national_id_number
                existing_profile.payout_method = payout_method
                existing_profile.payout_account_details = payout_account_details
                if national_id_number and existing_profile.kyc_status == SellerProfile.KycStatus.UNVERIFIED:
                    existing_profile.kyc_status = SellerProfile.KycStatus.PENDING
                existing_profile.save()
                profile = existing_profile
            else:
                profile = apply_for_seller_account(
                    user=user,
                    store_name=store_name,
                    national_id_number=national_id_number,
                    payout_method=payout_method,
                    payout_account_details=payout_account_details,
                    bio=bio,
                )

            if national_id_number:
                messages.success(request, f"Congratulations! Your store '{profile.store_name}' has been updated and your KYC identity verification is submitted for review.")
            else:
                messages.success(request, f"Congratulations! Your store '{profile.store_name}' is ready. You can start listing books immediately!")
            return redirect("seller_listings")

    return render(
        request,
        "accounts/seller_apply.html",
        {
            "seller_user": user,
            "seller_profile": existing_profile,
            "cart_count": cart_count,
        },
    )
