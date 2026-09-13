from django.conf import settings
from django.db import models
from apps.listings.models import BookListing


class Conversation(models.Model):
    """A direct inquiry thread between a buyer and seller regarding a specific used book listing."""
    listing = models.ForeignKey(BookListing, on_delete=models.CASCADE, related_name="conversations")
    buyer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="buyer_threads")
    seller = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="seller_threads")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-updated_at"]
        unique_together = ("listing", "buyer", "seller")
        verbose_name = "Conversation"
        verbose_name_plural = "Conversations"

    def __str__(self) -> str:
        return f"Inquiry on {self.listing.book.title} ({self.buyer.email} -> {self.seller.email})"


class InquiryMessage(models.Model):
    conversation = models.ForeignKey(Conversation, on_delete=models.CASCADE, related_name="messages")
    sender = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    text = models.TextField()
    photo_evidence = models.ImageField(upload_to="inquiry_attachments/", blank=True, null=True)
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]
        verbose_name = "Inquiry Message"
        verbose_name_plural = "Inquiry Messages"

    def __str__(self) -> str:
        return f"Msg from {self.sender.email} at {self.created_at.strftime('%H:%M')}"
