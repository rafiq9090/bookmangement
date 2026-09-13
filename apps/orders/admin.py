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
