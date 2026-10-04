from django.contrib import admin
from apps.orders.models import Cart, CartItem, Order, OrderItem, OrderShipment


class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0
    readonly_fields = ("listing", "price_at_purchase")


class OrderShipmentInline(admin.TabularInline):
    model = OrderShipment
    extra = 0
    show_change_link = True


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ("id", "buyer", "total_amount", "shipping_total", "status", "created_at")
    list_filter = ("status", "created_at")
    search_fields = ("id", "buyer__email")
    inlines = [OrderShipmentInline]


@admin.register(OrderShipment)
class OrderShipmentAdmin(admin.ModelAdmin):
    list_display = ("id", "order", "seller", "courier_name", "tracking_number", "shipping_fee", "subtotal", "status")
    list_filter = ("status", "courier_name")
    search_fields = ("tracking_number", "seller__email")
    inlines = [OrderItemInline]


@admin.register(Cart)
class CartAdmin(admin.ModelAdmin):
    list_display = ("user", "created_at", "updated_at")


from apps.orders.models import PurchaseAgreement, SellerReview, MarketplaceReport, MarketplaceNotification

@admin.register(PurchaseAgreement)
class PurchaseAgreementAdmin(admin.ModelAdmin):
    list_display = ("id", "listing", "status", "buyer", "seller", "accepted_price")
    list_filter = ("status",)
    readonly_fields = tuple(field.name for field in PurchaseAgreement._meta.fields)
    def has_add_permission(self, request):
        return False
    def has_delete_permission(self, request, obj=None):
        return False

@admin.register(MarketplaceReport)
class MarketplaceReportAdmin(admin.ModelAdmin):
    list_display = ("id", "reporter", "listing", "status", "created_at", "resolve_link")
    list_filter = ("status",)
    readonly_fields = ("reporter", "listing", "agreement", "details", "created_at")

    def resolve_link(self, obj):
        if not obj.agreement_id:
            return "Listing report"
        from django.urls import reverse
        from django.utils.html import format_html
        return format_html('<a href="{}">Resolve pickup</a>', reverse('resolve_pickup', args=[obj.agreement_id]))

admin.site.register(SellerReview)
admin.site.register(MarketplaceNotification)
