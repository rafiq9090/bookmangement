from datetime import timedelta
from decimal import Decimal
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework.exceptions import APIException
from apps.accounts.models import CustomUser
from apps.books.models import Book
from apps.listings.models import BookListing
from apps.orders.models import Cart, CartItem, PurchaseAgreement as Agreement, SellerReview, MarketplaceNotification
from apps.orders.services.pickup import create_purchase_request, act_on_agreement, expire_reservations


class PickupFlowTests(TestCase):
    def setUp(self):
        self.buyer = CustomUser.objects.create_user(email='buyer@pickup.test', password='pass')
        self.other = CustomUser.objects.create_user(email='other@pickup.test', password='pass')
        self.seller = CustomUser.objects.create_user(email='seller@pickup.test', password='pass')
        self.book = Book.objects.create(title='Old book')
        self.listing = BookListing.objects.create(book=self.book, seller=self.seller, price=500, district='Dhaka', area='Mirpur')
        self.agreement = create_purchase_request(self.buyer, self.listing.pk, '400.00')

    def reserve(self):
        return act_on_agreement(self.agreement.pk, self.seller, 'accept')

    def arrange(self):
        self.reserve()
        act_on_agreement(self.agreement.pk, self.buyer, 'propose_pickup', {
            'pickup_place': 'Public library', 'pickup_instructions': 'Front desk',
            'pickup_at': (timezone.now() + timedelta(days=3)).isoformat()})
        return act_on_agreement(self.agreement.pk, self.seller, 'accept_pickup')

    def test_price_and_mutual_completion(self):
        agreement = self.arrange()
        self.assertEqual(agreement.accepted_price, Decimal('400'))
        self.assertGreater(agreement.reservation_expires_at, agreement.pickup_at)
        act_on_agreement(agreement.pk, self.buyer, 'confirm')
        self.listing.refresh_from_db()
        self.assertEqual(self.listing.status, 'RESERVED')
        act_on_agreement(agreement.pk, self.seller, 'confirm')
        act_on_agreement(agreement.pk, self.seller, 'confirm')
        self.listing.refresh_from_db()
        self.assertEqual(self.listing.status, 'SOLD')
        self.assertEqual(Agreement.objects.count(), 1)
        act_on_agreement(agreement.pk, self.buyer, 'review', {'rating': 5})
        act_on_agreement(agreement.pk, self.buyer, 'review', {'rating': 5})
        self.assertEqual(SellerReview.objects.count(), 1)

    def test_competing_buyer_cannot_reserve(self):
        second = create_purchase_request(self.other, self.listing.pk)
        self.reserve()
        with self.assertRaises(APIException):
            act_on_agreement(second.pk, self.seller, 'accept')
        act_on_agreement(second.pk, self.other, 'cancel')
        self.listing.refresh_from_db()
        self.assertEqual(self.listing.status, 'RESERVED')

    def test_partial_handover_never_expires_or_cancels(self):
        self.arrange()
        act_on_agreement(self.agreement.pk, self.buyer, 'confirm')
        Agreement.objects.filter(pk=self.agreement.pk).update(reservation_expires_at=timezone.now()-timedelta(days=1))
        self.assertEqual(expire_reservations(), 0)
        with self.assertRaises(APIException):
            act_on_agreement(self.agreement.pk, self.seller, 'cancel')
        act_on_agreement(self.agreement.pk, self.seller, 'report', {'details':'Other party stopped responding'})
        self.listing.refresh_from_db()
        self.assertEqual(self.listing.status, 'RESERVED')

    def test_expiry_and_late_confirmation(self):
        self.reserve()
        Agreement.objects.filter(pk=self.agreement.pk).update(reservation_expires_at=timezone.now()-timedelta(seconds=1))
        result = act_on_agreement(self.agreement.pk, self.buyer, 'confirm')
        self.assertEqual(result.status, 'EXPIRED')
        self.listing.refresh_from_db()
        self.assertEqual(self.listing.status, 'ACTIVE')

    def test_private_api_and_ownership(self):
        self.arrange()
        client = APIClient()
        client.force_authenticate(self.other)
        self.assertEqual(client.get(f'/api/v1/pickups/{self.agreement.pk}/').status_code, 404)
        self.assertEqual(client.patch(f'/api/v1/listings/{self.listing.pk}/', {'price':'1'}, format='json').status_code, 403)
        client.force_authenticate(self.buyer)
        self.assertEqual(client.get(f'/api/v1/pickups/{self.agreement.pk}/').data['pickup_place'], 'Public library')
        self.assertEqual(client.post(f'/api/v1/pickups/{self.agreement.pk}/', {'action':'accept'}, format='json').status_code, 403)

    def test_nonblocking_carts(self):
        for user in (self.buyer, self.other):
            cart = Cart.objects.create(user=user)
            CartItem.objects.create(cart=cart, listing=self.listing)
        self.assertEqual(CartItem.objects.count(), 2)

    def test_notifications_and_view_render(self):
        self.assertTrue(MarketplaceNotification.objects.filter(user=self.seller).exists())
        self.client.force_login(self.buyer)
        for url in ['/pickups/', f'/pickups/{self.agreement.pk}/', '/store/', f'/books/{self.book.slug}/', '/sell/', f'/inbox/{self.agreement.conversation_id}/']:
            self.assertEqual(self.client.get(url).status_code, 200, url)

    def test_legacy_money_endpoints_disabled(self):
        self.client.force_login(self.buyer)
        self.assertRedirects(self.client.get('/checkout/'), '/pickups/')
        client = APIClient()
        client.force_authenticate(self.buyer)
        self.assertEqual(client.post('/api/v1/orders/checkout/', {}, format='json').status_code, 409)

    def test_invalid_offer_and_self_purchase(self):
        for value in ['NaN', '-1', '0', '1.001']:
            with self.assertRaises(APIException):
                create_purchase_request(self.buyer, self.listing.pk, value)
        with self.assertRaises(APIException):
            create_purchase_request(self.seller, self.listing.pk)

    def test_cancelled_request_can_be_requested_again(self):
        act_on_agreement(self.agreement.pk, self.buyer, 'cancel')
        fresh = create_purchase_request(self.buyer, self.listing.pk, '350')
        self.assertNotEqual(fresh.pk, self.agreement.pk)
        self.assertEqual(fresh.offered_price, Decimal('350'))

    def test_dispute_resolution_requires_staff_and_reason(self):
        from apps.orders.services.pickup import resolve_dispute
        self.arrange()
        act_on_agreement(self.agreement.pk, self.buyer, 'confirm')
        act_on_agreement(self.agreement.pk, self.seller, 'report', {'details':'Confirmation missing'})
        with self.assertRaises(APIException):
            resolve_dispute(self.agreement.pk, self.other, 'cancelled', 'No handover')
        admin = CustomUser.objects.create_user(email='admin@pickup.test', password='pass', is_staff=True)
        resolved = resolve_dispute(self.agreement.pk, admin, 'completed', 'Both parties provided evidence of handover.')
        self.assertEqual(resolved.status, 'COMPLETED')
        self.listing.refresh_from_db()
        self.assertEqual(self.listing.status, 'SOLD')

    def test_condition_migration_preserves_unknown_grade(self):
        from importlib import import_module
        from django.apps import apps
        self.listing.condition = 'COLLECTIBLE'
        self.listing.save()
        migration = import_module('apps.listings.migrations.0003_preserve_collectible_condition')
        migration.preserve_collectibles(apps, None)
        self.listing.refresh_from_db()
        self.assertTrue(self.listing.is_collectible)
        self.assertTrue(self.listing.condition_needs_review)
        self.assertEqual(self.listing.condition, 'COLLECTIBLE')
        with self.assertRaises(APIException):
            create_purchase_request(self.other, self.listing.pk)

    def test_exact_pickup_pin_stays_private(self):
        self.reserve()
        act_on_agreement(self.agreement.pk, self.buyer, 'propose_pickup', {
            'pickup_place': 'Library', 'pickup_at': (timezone.now()+timedelta(days=1)).isoformat(),
            'pickup_latitude': '23.812345', 'pickup_longitude': '90.412345'})
        client = APIClient()
        client.force_authenticate(self.buyer)
        detail = client.get(f'/api/v1/pickups/{self.agreement.pk}/').data
        self.assertEqual(detail['pickup_latitude'], '23.812345')
        public = client.get(f'/api/v1/listings/{self.listing.pk}/').data
        self.assertNotIn('pickup_latitude', public)
        self.assertNotIn('pickup_place', public)

    def test_public_pin_is_rounded_and_invalid_api_input_rejected(self):
        from apps.listings.forms import ListingLocationForm
        form = ListingLocationForm({'district':'Dhaka', 'area':'Mirpur', 'latitude':'23.812345', 'longitude':'90.412345'})
        self.assertTrue(form.is_valid())
        self.assertEqual(form.cleaned_data['latitude'], Decimal('23.81'))
        client = APIClient()
        client.force_authenticate(self.buyer)
        self.assertEqual(client.post('/api/v1/pickups/', {'listing_id':'invalid'}, format='json').status_code, 400)

    def test_password_reset_and_listing_edit_pages_render(self):
        self.assertEqual(self.client.get('/password-reset/').status_code, 200)
        self.client.force_login(self.seller)
        self.assertEqual(self.client.get(f'/seller/listings/{self.listing.pk}/edit/').status_code, 200)

    def test_api_draft_publishes_only_after_valid_photo(self):
        from io import BytesIO
        from PIL import Image
        from django.core.files.uploadedfile import SimpleUploadedFile
        from unittest.mock import patch
        client = APIClient()
        client.force_authenticate(self.other)
        result = client.post('/api/v1/listings/', {'book':self.book.pk, 'price':'200', 'district':'Dhaka', 'area':'Mirpur'}, format='json')
        self.assertEqual(result.status_code, 201)
        listing = BookListing.objects.get(pk=result.data['id'])
        self.assertEqual(listing.status, 'DRAFT')
        buf = BytesIO()
        Image.new('RGB', (10,10)).save(buf, format='PNG')
        photo = SimpleUploadedFile('copy.png', buf.getvalue(), content_type='image/png')
        # Test storage is isolated from user uploads.
        import tempfile
        with tempfile.TemporaryDirectory() as directory:
            with self.settings(MEDIA_ROOT=directory), patch('apps.listings.tasks.queue_listing_image'):
                result = client.post(f'/api/v1/listings/{listing.pk}/images/', {'image':photo}, format='multipart')
                self.assertEqual(result.status_code, 201)
                listing.refresh_from_db()
                self.assertEqual(listing.status, 'ACTIVE')

    def test_public_detail_does_not_expose_seller_contact(self):
        self.seller.phone_number = '01712345678'
        self.seller.save()
        result = self.client.get(f'/books/{self.book.slug}/')
        self.assertNotContains(result, self.seller.phone_number)
        self.assertNotContains(result, self.seller.email)


from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from django.db import close_old_connections
from django.test import TransactionTestCase, skipUnlessDBFeature

class PickupConcurrencyTests(TransactionTestCase):
    @skipUnlessDBFeature('has_select_for_update')
    def test_simultaneous_acceptances_reserve_only_one_buyer(self):
        seller = CustomUser.objects.create_user(email='concurrent-seller@pickup.test')
        buyers = [CustomUser.objects.create_user(email=f'concurrent-{i}@pickup.test') for i in range(2)]
        listing = BookListing.objects.create(book=Book.objects.create(title='Only copy'), seller=seller, price=100)
        agreements = [create_purchase_request(buyer, listing.pk) for buyer in buyers]
        barrier = Barrier(2)
        def accept(pk):
            close_old_connections()
            try:
                actor = CustomUser.objects.get(pk=seller.pk)
                barrier.wait(timeout=10)
                try:
                    act_on_agreement(pk, actor, 'accept')
                    return 'accepted'
                except APIException:
                    return 'rejected'
            finally:
                close_old_connections()
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(accept, [agreement.pk for agreement in agreements]))
        self.assertCountEqual(results, ['accepted', 'rejected'])
        self.assertEqual(Agreement.objects.filter(listing=listing, status='RESERVED').count(), 1)
