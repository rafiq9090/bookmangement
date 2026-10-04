"""Thin HTTP adapters: lifecycle decisions live in services.pickup."""
from decimal import Decimal
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.db import transaction
from django.core.paginator import Paginator
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST
from rest_framework import permissions, serializers
from rest_framework.exceptions import APIException
from rest_framework.response import Response
from rest_framework.views import APIView
from drf_spectacular.utils import extend_schema
from apps.listings.models import BookListing
from apps.orders.models import PurchaseAgreement, MarketplaceNotification, MarketplaceReport
from apps.orders.services.pickup import create_purchase_request, act_on_agreement


class AgreementSerializer(serializers.ModelSerializer):
    class Meta:
        model = PurchaseAgreement
        fields = ('id', 'conversation', 'listing', 'buyer', 'seller', 'offered_price', 'accepted_price', 'status',
                  'reservation_expires_at', 'pickup_place', 'pickup_instructions', 'pickup_at', 'pickup_proposed_by',
                  'pickup_latitude', 'pickup_longitude', 'pickup_accepted_at', 'buyer_confirmed_at', 'seller_confirmed_at')
        read_only_fields = fields



class PurchaseRequestSerializer(serializers.Serializer):
    listing_id = serializers.IntegerField(min_value=1)
    offered_price = serializers.DecimalField(max_digits=8, decimal_places=2, min_value=Decimal("0.01"), required=False)


class AgreementActionSerializer(serializers.Serializer):
    action = serializers.ChoiceField(choices=['accept', 'decline', 'cancel', 'propose_pickup', 'accept_pickup', 'confirm', 'report', 'review'])
    pickup_place = serializers.CharField(max_length=255, required=False)
    pickup_instructions = serializers.CharField(max_length=2000, required=False, allow_blank=True)
    pickup_at = serializers.DateTimeField(required=False)
    pickup_latitude = serializers.DecimalField(max_digits=9, decimal_places=6, required=False, min_value=-90, max_value=90)
    pickup_longitude = serializers.DecimalField(max_digits=9, decimal_places=6, required=False, min_value=-180, max_value=180)
    details = serializers.CharField(max_length=4000, required=False)
    rating = serializers.IntegerField(min_value=1, max_value=5, required=False)
    comment = serializers.CharField(max_length=2000, required=False, allow_blank=True)


def clean_api_exception(exc):
    detail = getattr(exc, 'detail', str(exc))
    if isinstance(detail, (list, tuple)):
        return " ".join(str(d) for d in detail)
    elif isinstance(detail, dict):
        parts = []
        for k, v in detail.items():
            val_str = " ".join(str(i) for i in v) if isinstance(v, (list, tuple)) else str(v)
            parts.append(f"{k.replace('_', ' ').capitalize()}: {val_str}")
        return " ".join(parts)
    return str(detail)


def participant_agreement(user, pk):
    return get_object_or_404(PurchaseAgreement.objects.select_related('listing__book', 'conversation'),
                            Q(buyer=user) | Q(seller=user), pk=pk)


@login_required(login_url='/login/')
def pickup_list(request):
    agreements = PurchaseAgreement.objects.filter(Q(buyer=request.user) | Q(seller=request.user)).select_related('listing__book')
    agreements = Paginator(agreements.order_by("-created_at"), 25).get_page(request.GET.get("page"))
    notifications = MarketplaceNotification.objects.filter(user=request.user)[:30]
    return render(request, 'orders/pickup_list.html', {'agreements': agreements, 'notifications': notifications, 'page_obj': agreements})


@login_required(login_url='/login/')
def pickup_detail(request, pk):
    agreement = participant_agreement(request.user, pk)
    if request.method == 'POST':
        try:
            act_on_agreement(agreement.pk, request.user, request.POST.get('action'), request.POST)
            messages.success(request, 'Purchase agreement updated.')
        except APIException as exc:
            messages.error(request, clean_api_exception(exc))
        return redirect('pickup_detail', pk=pk)
    MarketplaceNotification.objects.filter(user=request.user, conversation=agreement.conversation).update(is_read=True)
    return render(request, 'orders/pickup_detail.html', {'agreement': agreement})


@login_required(login_url='/login/')
@require_POST
def request_purchase(request, listing_id):
    listing = get_object_or_404(BookListing, pk=listing_id, is_deleted=False)
    try:
        agreement = create_purchase_request(request.user, listing.pk, request.POST.get('offered_price'))
    except APIException as exc:
        messages.error(request, clean_api_exception(exc))
        return redirect('book_detail', slug=listing.book.slug)
    return redirect('pickup_detail', pk=agreement.pk)


@login_required(login_url='/login/')
@require_POST
def report_listing(request, listing_id):
    from apps.accounts.submission_limits import limit_submission
    blocked = limit_submission(request, 'listing-report', limit=10)
    if blocked is not None:
        return blocked
    listing = get_object_or_404(BookListing, pk=listing_id, is_deleted=False)
    details = request.POST.get('details', '').strip()
    if not details or len(details) > 4000:
        messages.error(request, 'Describe the problem in 1–4,000 characters.')
    else:
        from apps.accounts.models import CustomUser
        with transaction.atomic():
            CustomUser.objects.select_for_update().get(pk=request.user.pk)
            if MarketplaceReport.objects.filter(reporter=request.user, listing=listing, status='PENDING').exists():
                messages.info(request, 'Your report for this listing is already awaiting review.')
            else:
                MarketplaceReport.objects.create(reporter=request.user, listing=listing, details=details)
                messages.success(request, 'Report submitted for moderation.')
    return redirect('book_detail', slug=listing.book.slug)


class AgreementListAPI(APIView):
    serializer_class = AgreementSerializer
    permission_classes = [permissions.IsAuthenticated]
    @extend_schema(operation_id="pickup_agreements_list", responses=AgreementSerializer(many=True))
    def get(self, request):
        agreements = PurchaseAgreement.objects.filter(Q(buyer=request.user) | Q(seller=request.user))
        return Response(AgreementSerializer(agreements, many=True).data)
    @extend_schema(operation_id="pickup_agreement_request", request=PurchaseRequestSerializer, responses={201: AgreementSerializer})
    def post(self, request):
        serializer = PurchaseRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        listing = get_object_or_404(BookListing, pk=data['listing_id'], is_deleted=False)
        agreement = create_purchase_request(request.user, listing.pk, data.get('offered_price'))
        return Response(AgreementSerializer(agreement).data, status=201)


class AgreementDetailAPI(APIView):
    serializer_class = AgreementSerializer
    permission_classes = [permissions.IsAuthenticated]
    @extend_schema(operation_id="pickup_agreement_detail", responses=AgreementSerializer)
    def get(self, request, pk):
        return Response(AgreementSerializer(participant_agreement(request.user, pk)).data)
    @extend_schema(operation_id="pickup_agreement_action", request=AgreementActionSerializer, responses=AgreementSerializer)
    def post(self, request, pk):
        agreement = participant_agreement(request.user, pk)
        serializer = AgreementActionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        agreement = act_on_agreement(agreement.pk, request.user, data['action'], data)
        return Response(AgreementSerializer(agreement).data)


from django.contrib.admin.views.decorators import staff_member_required

@staff_member_required
def resolve_pickup(request, pk):
    from django.core.exceptions import PermissionDenied
    if not request.user.has_perm('orders.change_purchaseagreement'):
        raise PermissionDenied('Your admin role cannot resolve disputes.')
    agreement = get_object_or_404(PurchaseAgreement.objects.select_related('listing__book'), pk=pk)
    if request.method == 'POST':
        from apps.orders.services.pickup import resolve_dispute
        try:
            from django.db import transaction
            from apps.accounts.models import AdminActivity
            with transaction.atomic():
                before = agreement.status
                result = resolve_dispute(pk, request.user, request.POST.get('outcome'), request.POST.get('note', ''))
                AdminActivity.objects.create(actor=request.user, action='resolve_pickup', target=f'pickup:{pk}',
                    reason=request.POST.get('note', ''), before={'status': before}, after={'status': result.status})
            messages.success(request, 'Resolution recorded and participants notified.')
            return redirect('/admin/dashboard/?tab=pickups')
        except APIException as exc:
            messages.error(request, str(exc.detail))
    return render(request, 'orders/resolve_pickup.html', {'agreement': agreement})
