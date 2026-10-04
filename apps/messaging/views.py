from django.db.models import Q
from rest_framework import generics, permissions, status
from rest_framework.exceptions import PermissionDenied
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.listings.models import BookListing
from apps.messaging.models import Conversation, InquiryMessage
from apps.messaging.serializers import ConversationSerializer, InquiryMessageSerializer, ConversationCreateSerializer


class ConversationListCreateView(generics.ListCreateAPIView):
    serializer_class = ConversationSerializer
    permission_classes = (permissions.IsAuthenticated,)

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return Conversation.objects.none()
        user = self.request.user
        return (
            Conversation.objects.filter(Q(buyer=user) | Q(seller=user))
            .select_related("listing__book", "buyer", "seller__seller_profile")
        )

    def create(self, request: Request, *args, **kwargs) -> Response:
        payload = ConversationCreateSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        listing_id = payload.validated_data["listing_id"]
        try:
            listing = BookListing.objects.select_related("seller").get(id=listing_id)
        except BookListing.DoesNotExist:
            return Response({"error": "Listing not found."}, status=status.HTTP_404_NOT_FOUND)

        if listing.is_deleted or listing.status != BookListing.Status.ACTIVE:
            return Response({"error": "This copy is not available."}, status=status.HTTP_400_BAD_REQUEST)

        if listing.seller == request.user:
            return Response({"error": "Cannot open inquiry with yourself."}, status=status.HTTP_400_BAD_REQUEST)

        conversation, _ = Conversation.objects.get_or_create(
            listing=listing,
            buyer=request.user,
            seller=listing.seller,
        )

        initial_text = payload.validated_data.get("message", "").strip()
        if initial_text:
            InquiryMessage.objects.create(
                conversation=conversation,
                sender=request.user,
                text=initial_text,
            )

        return Response(ConversationSerializer(conversation).data, status=status.HTTP_201_CREATED)


from drf_spectacular.utils import extend_schema


class InquiryMessageSendView(APIView):
    serializer_class = InquiryMessageSerializer
    permission_classes = (permissions.IsAuthenticated,)

    @extend_schema(request=InquiryMessageSerializer, responses={201: InquiryMessageSerializer})
    def post(self, request: Request, conversation_id: int) -> Response:
        try:
            conversation = Conversation.objects.get(id=conversation_id)
        except Conversation.DoesNotExist:
            return Response({"error": "Conversation not found."}, status=status.HTTP_404_NOT_FOUND)

        user = request.user
        if user != conversation.buyer and user != conversation.seller:
            raise PermissionDenied("You are not a participant in this conversation.")

        serializer = InquiryMessageSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        text = serializer.validated_data["text"].strip()
        if not text:
            return Response({"error": "Message text is required."}, status=status.HTTP_400_BAD_REQUEST)

        if len(text) > 5000:
            return Response({"error": "Messages must be at most 5000 characters."}, status=400)
        msg = InquiryMessage.objects.create(
            conversation=conversation,
            sender=user,
            text=text,
            photo_evidence=serializer.validated_data.get("photo_evidence"),
        )
        from apps.orders.services.pickup import notify
        notify(conversation, user, "New message about " + conversation.listing.book.title[:180])
        conversation.save(update_fields=["updated_at"])

        return Response(InquiryMessageSerializer(msg).data, status=status.HTTP_201_CREATED)
