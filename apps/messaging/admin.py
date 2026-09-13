from django.contrib import admin
from apps.messaging.models import Conversation, InquiryMessage


class InquiryMessageInline(admin.TabularInline):
    model = InquiryMessage
    extra = 0
    readonly_fields = ("sender", "text", "created_at")


@admin.register(Conversation)
class ConversationAdmin(admin.ModelAdmin):
    list_display = ("id", "listing", "buyer", "seller", "created_at", "updated_at")
    search_fields = ("listing__book__title", "buyer__email", "seller__email")
    inlines = [InquiryMessageInline]
