from rest_framework import generics, permissions, status, viewsets
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework_simplejwt.tokens import RefreshToken

from .models import Address, CustomUser
from .serializers import (
    AddressSerializer,
    SellerProfileSerializer,
    UserProfileSerializer,
    UserRegisterSerializer,
)
from .services.users import apply_for_seller_account


class RegisterView(generics.CreateAPIView):
    serializer_class = UserRegisterSerializer
    permission_classes = (permissions.AllowAny,)

    def create(self, request: Request, *args, **kwargs) -> Response:
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user: CustomUser = serializer.save()

        refresh = RefreshToken.for_user(user)
        return Response(
            {
                "user": UserProfileSerializer(user).data,
                "tokens": {
                    "refresh": str(refresh),
                    "access": str(refresh.access_token),
                },
            },
            status=status.HTTP_201_CREATED,
        )


class CurrentUserView(generics.RetrieveUpdateAPIView):
    serializer_class = UserProfileSerializer
    permission_classes = (permissions.IsAuthenticated,)

    def get_object(self) -> CustomUser:
        return self.request.user


class SellerApplicationView(generics.CreateAPIView):
    serializer_class = SellerProfileSerializer
    permission_classes = (permissions.IsAuthenticated,)

    def create(self, request: Request, *args, **kwargs) -> Response:
        profile = apply_for_seller_account(
            user=request.user,
            store_name=request.data.get("store_name", "").strip(),
            national_id_number=request.data.get("national_id_number", "").strip(),
            payout_method=request.data.get("payout_method", "BKASH"),
            payout_account_details=request.data.get("payout_account_details", "").strip(),
            bio=request.data.get("bio", "").strip(),
        )
        return Response(SellerProfileSerializer(profile).data, status=status.HTTP_201_CREATED)


class AddressViewSet(viewsets.ModelViewSet):
    serializer_class = AddressSerializer
    permission_classes = (permissions.IsAuthenticated,)

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return Address.objects.none()
        return Address.objects.filter(user=self.request.user)

    def perform_create(self, serializer: AddressSerializer) -> None:
        serializer.save(user=self.request.user)
