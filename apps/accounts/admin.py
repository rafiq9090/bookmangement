from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import Address, CustomUser, SellerProfile


@admin.register(CustomUser)
class CustomUserAdmin(UserAdmin):
    model = CustomUser
    list_display = ("email", "first_name", "last_name", "is_seller", "is_staff", "is_active")
    list_filter = ("is_seller", "is_staff", "is_active")
    ordering = ("email",)
    fieldsets = (
        (None, {"fields": ("email", "password")}),
        ("Personal info", {"fields": ("first_name", "last_name", "phone_number", "avatar")}),
        ("Permissions", {"fields": ("is_seller", "is_active", "is_staff", "is_superuser", "groups", "user_permissions")}),
        ("Important dates", {"fields": ("last_login", "date_joined")}),
    )
    add_fieldsets = (
        (None, {
            "classes": ("wide",),
            "fields": ("email", "password", "is_seller"),
        }),
    )


@admin.register(SellerProfile)
class SellerProfileAdmin(admin.ModelAdmin):
    list_display = ("store_name", "user", "kyc_status", "payout_method", "rating_avg", "created_at")
    list_filter = ("kyc_status", "payout_method")
    search_fields = ("store_name", "user__email", "national_id_number")


@admin.register(Address)
class AddressAdmin(admin.ModelAdmin):
    list_display = ("recipient_name", "user", "city", "country", "is_default")
    list_filter = ("is_default", "city", "country")
