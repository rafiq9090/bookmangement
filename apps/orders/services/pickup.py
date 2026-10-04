"""All pickup transitions lock the listing first, then its agreement.

This consistent lock order protects competing requests on PostgreSQL. Views must
never update agreement/listing lifecycle fields directly.
"""
from datetime import timedelta
from decimal import Decimal, InvalidOperation
from django.conf import settings
from django.db import transaction
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from rest_framework.exceptions import PermissionDenied, ValidationError
from apps.listings.models import BookListing
from apps.messaging.models import Conversation
from apps.orders.models import PurchaseAgreement as Agreement, MarketplaceNotification, MarketplaceReport, SellerReview

LIVE = [Agreement.Status.RESERVED, Agreement.Status.PICKUP_AGREED]


def price_value(value):
    try:
        price = Decimal(str(value))
        if not price.is_finite() or price <= 0 or price > Decimal('999999.99') or price != price.quantize(Decimal('.01')):
            raise ValueError
        return price
    except (InvalidOperation, ValueError, TypeError):
        raise ValidationError('Enter a positive price with at most two decimal places.')


def notify(conversation, actor, text):
    recipient = conversation.seller if actor.pk == conversation.buyer_id else conversation.buyer
    MarketplaceNotification.objects.create(user=recipient, conversation=conversation, text=text)


@transaction.atomic
def create_purchase_request(buyer, listing_id, offered_price=None):
    if not buyer.is_authenticated or not buyer.is_active:
        raise PermissionDenied('An active account is required.')
    listing = BookListing.objects.select_for_update().get(pk=listing_id, is_deleted=False)
    if buyer.pk == listing.seller_id:
        raise ValidationError('You cannot buy your own listing.')
    if listing.status != BookListing.Status.ACTIVE or listing.condition_needs_review:
        raise ValidationError('This copy is unavailable or needs a condition review.')
    conversation, _ = Conversation.objects.get_or_create(listing=listing, buyer=buyer, seller=listing.seller)
    agreement = Agreement.objects.filter(conversation=conversation, status=Agreement.Status.REQUESTED).first()
    amount = price_value(offered_price if offered_price not in (None, '') else listing.price)
    if agreement is None:
        agreement = Agreement.objects.create(conversation=conversation, listing=listing, buyer=buyer,
                                             seller=listing.seller, offered_price=amount)
    else:
        agreement.offered_price = amount
        agreement.save(update_fields=['offered_price', 'updated_at'])
    notify(conversation, buyer, 'New purchase request or updated offer.')
    return agreement


def expire_locked(agreement, listing):
    if agreement.status in LIVE and agreement.reservation_expires_at and agreement.reservation_expires_at <= timezone.now():
        agreement.status = Agreement.Status.EXPIRED
        agreement.save(update_fields=['status', 'updated_at'])
        if listing.status == BookListing.Status.RESERVED:
            listing.status = BookListing.Status.ACTIVE
            listing.save(update_fields=['status', 'updated_at'])
        return True
    return False


@transaction.atomic
def act_on_agreement(agreement_id, actor, action, data=None):
    data = data or {}
    listing_id = Agreement.objects.values_list('listing_id', flat=True).get(pk=agreement_id)
    listing = BookListing.objects.select_for_update().get(pk=listing_id)
    agreement = Agreement.objects.select_for_update().select_related('conversation').get(pk=agreement_id)
    if not actor.is_authenticated or not actor.is_active or actor.pk not in (agreement.buyer_id, agreement.seller_id):
        raise PermissionDenied('Only the buyer and seller can access this agreement.')
    if expire_locked(agreement, listing):
        return agreement
    now = timezone.now()
    if action == 'accept':
        if actor.pk != agreement.seller_id:
            raise PermissionDenied('Only the seller can accept an offer.')
        if agreement.status in LIVE:
            return agreement
        if agreement.status != Agreement.Status.REQUESTED or listing.status != BookListing.Status.ACTIVE or listing.is_deleted:
            raise ValidationError('This copy cannot be reserved.')
        agreement.accepted_price = agreement.offered_price
        agreement.status = Agreement.Status.RESERVED
        agreement.reservation_expires_at = now + timedelta(hours=settings.PICKUP_RESERVATION_HOURS)
        listing.status = BookListing.Status.RESERVED
        listing.save(update_fields=['status', 'updated_at'])
    elif action == 'decline':
        if actor.pk != agreement.seller_id:
            raise PermissionDenied('Only the seller can decline.')
        if agreement.status != Agreement.Status.REQUESTED:
            raise ValidationError('Only pending requests can be declined.')
        agreement.status = Agreement.Status.DECLINED
    elif action == 'cancel':
        if agreement.status == Agreement.Status.CANCELLED:
            return agreement
        if agreement.status not in [Agreement.Status.REQUESTED, *LIVE]:
            raise ValidationError('After handover starts, report a problem instead of cancelling.')
        agreement.status = Agreement.Status.CANCELLED
        # A requested agreement does not own another buyer\'s reservation.
        if agreement.accepted_price is not None and listing.status == BookListing.Status.RESERVED:
            listing.status = BookListing.Status.ACTIVE
            listing.save(update_fields=['status', 'updated_at'])
    elif action == 'propose_pickup':
        if agreement.status not in LIVE:
            raise ValidationError('Reserve this copy before arranging pickup.')
        scheduled = parse_datetime(str(data.get('pickup_at', '')))
        if scheduled is None:
            raise ValidationError('Provide a valid pickup time.')
        if timezone.is_naive(scheduled):
            scheduled = timezone.make_aware(scheduled, timezone.get_fixed_timezone(360))
        place = str(data.get('pickup_place', '')).strip()
        if not place:
            raise ValidationError('Please enter a public meeting place.')
        if len(place) > 255:
            raise ValidationError('Meeting place cannot exceed 255 characters.')
        if scheduled <= now:
            raise ValidationError('Meeting time must be in the future (please pick an upcoming date and time).')
        if scheduled > now + timedelta(days=14):
            raise ValidationError('Meeting time must be within the next 14 days.')
        latitude, longitude = data.get('pickup_latitude'), data.get('pickup_longitude')
        has_latitude, has_longitude = latitude not in (None, ""), longitude not in (None, "")
        if has_latitude != has_longitude:
            raise ValidationError('Provide both pickup coordinates or neither.')
        if has_latitude and has_longitude:
            try:
                latitude, longitude = Decimal(str(latitude)), Decimal(str(longitude))
                if not latitude.is_finite() or not longitude.is_finite() or not -90 <= latitude <= 90 or not -180 <= longitude <= 180:
                    raise ValueError
                latitude, longitude = latitude.quantize(Decimal('.000001')), longitude.quantize(Decimal('.000001'))
            except (ValueError, InvalidOperation):
                raise ValidationError('Invalid pickup coordinates.')
        else:
            latitude, longitude = None, None
        agreement.pickup_latitude, agreement.pickup_longitude = latitude, longitude
        agreement.pickup_place = place
        agreement.pickup_at = scheduled
        agreement.pickup_instructions = str(data.get('pickup_instructions', ''))[:2000]
        agreement.pickup_proposed_by = actor
        agreement.pickup_accepted_at = None
        agreement.status = Agreement.Status.RESERVED
    elif action == 'accept_pickup':
        if agreement.status == Agreement.Status.PICKUP_AGREED:
            return agreement
        if agreement.status not in LIVE or not agreement.pickup_at or agreement.pickup_at <= now or actor.pk == agreement.pickup_proposed_by_id:
            raise ValidationError('The other participant must accept a future pickup proposal.')
        agreement.pickup_accepted_at = now
        agreement.reservation_expires_at = max(agreement.reservation_expires_at, agreement.pickup_at + timedelta(hours=24))
        agreement.status = Agreement.Status.PICKUP_AGREED
    elif action == 'confirm':
        if agreement.status == Agreement.Status.COMPLETED:
            return agreement
        if agreement.status not in [Agreement.Status.PICKUP_AGREED, Agreement.Status.AWAITING_CONFIRMATION]:
            raise ValidationError('Agree on pickup before confirming handover.')
        field = 'buyer_confirmed_at' if actor.pk == agreement.buyer_id else 'seller_confirmed_at'
        if getattr(agreement, field):
            return agreement
        setattr(agreement, field, now)
        agreement.status = Agreement.Status.AWAITING_CONFIRMATION
        if agreement.buyer_confirmed_at and agreement.seller_confirmed_at:
            agreement.status = Agreement.Status.COMPLETED
            listing.status = BookListing.Status.SOLD
            listing.save(update_fields=['status', 'updated_at'])
    elif action == 'report':
        details = str(data.get('details', '')).strip()
        if not details:
            raise ValidationError('Describe the problem.')
        MarketplaceReport.objects.create(reporter=actor, listing=listing, agreement=agreement, details=details[:4000])
        if agreement.status in [*LIVE, Agreement.Status.AWAITING_CONFIRMATION]:
            agreement.status = Agreement.Status.DISPUTED
            agreement.problem_details = details[:4000]
    elif action == 'review':
        if actor.pk != agreement.buyer_id or agreement.status != Agreement.Status.COMPLETED:
            raise PermissionDenied('Only the buyer of a completed purchase can review the seller.')
        try:
            rating = int(data.get('rating', 0))
        except (TypeError, ValueError):
            raise ValidationError('Choose a rating from 1 to 5.')
        if not 1 <= rating <= 5:
            raise ValidationError('Choose a rating from 1 to 5.')
        SellerReview.objects.get_or_create(agreement=agreement, defaults={'rating': rating, 'comment': str(data.get('comment', ''))[:2000]})
        return agreement
    else:
        raise ValidationError('Unknown agreement action.')
    agreement.save()
    notify(agreement.conversation, actor, 'Pickup agreement updated: ' + agreement.get_status_display())
    return agreement


def expire_reservations():
    count = 0
    ids = Agreement.objects.filter(status__in=LIVE, reservation_expires_at__lte=timezone.now()).values_list('pk', flat=True)
    for agreement_id in list(ids):
        with transaction.atomic():
            listing_id = Agreement.objects.values_list('listing_id', flat=True).get(pk=agreement_id)
            listing = BookListing.objects.select_for_update().get(pk=listing_id)
            agreement = Agreement.objects.select_for_update().get(pk=agreement_id)
            count += int(expire_locked(agreement, listing))
    return count


@transaction.atomic
def resolve_dispute(agreement_id, admin_user, outcome, note):
    """Explicit audited resolution. A disputed copy never returns to stock by timer."""
    if not admin_user.is_active or not admin_user.is_staff:
        raise PermissionDenied("Staff access required.")
    if outcome not in ("completed", "cancelled") or not str(note).strip():
        raise ValidationError("Choose an outcome and record the reason.")
    listing_id = Agreement.objects.values_list('listing_id', flat=True).get(pk=agreement_id)
    listing = BookListing.objects.select_for_update().get(pk=listing_id)
    agreement = Agreement.objects.select_for_update().get(pk=agreement_id)
    if agreement.status != Agreement.Status.DISPUTED:
        raise ValidationError("Only disputed agreements can be resolved.")
    agreement.status = Agreement.Status.COMPLETED if outcome == "completed" else Agreement.Status.CANCELLED
    listing.status = BookListing.Status.SOLD if outcome == "completed" else BookListing.Status.ACTIVE
    listing.save(update_fields=['status', 'updated_at'])
    agreement.save(update_fields=['status', 'updated_at'])
    MarketplaceReport.objects.create(reporter=admin_user, listing=listing, agreement=agreement,
        details="Admin resolution: " + outcome, status=MarketplaceReport.Status.RESOLVED, resolution=str(note)[:4000])
    MarketplaceReport.objects.filter(agreement=agreement, status=MarketplaceReport.Status.PENDING).update(
        status=MarketplaceReport.Status.RESOLVED, resolution=str(note)[:4000])
    for user in (agreement.buyer, agreement.seller):
        MarketplaceNotification.objects.create(user=user, conversation=agreement.conversation,
            text="Disputed pickup resolved: " + agreement.get_status_display())
    return agreement
