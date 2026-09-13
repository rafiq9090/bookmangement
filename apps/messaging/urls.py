from django.urls import path
from apps.messaging.views import ConversationListCreateView, InquiryMessageSendView

app_name = "messaging"

urlpatterns = [
    path("conversations/", ConversationListCreateView.as_view(), name="conversation-list"),
    path("conversations/<int:conversation_id>/reply/", InquiryMessageSendView.as_view(), name="reply"),
]
