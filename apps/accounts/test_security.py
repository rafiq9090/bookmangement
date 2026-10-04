from io import BytesIO
from unittest.mock import patch

from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, RequestFactory, override_settings
from PIL import Image

from apps.accounts.models import CustomUser
from config.security import clean_image, safe_next


class SecurityBoundaryTests(TestCase):
    def setUp(self):
        cache.clear()

    def tearDown(self):
        cache.clear()

    def test_redirects_reject_external_and_protocol_relative_urls(self):
        factory = RequestFactory()
        for value in ('https://attacker.example/', '//attacker.example/', 'https://testserver.attacker.example/'):
            self.assertEqual(safe_next(factory.get('/login/', {'next': value})), '/profile/')
        self.assertEqual(safe_next(factory.get('/login/', {'next': '/pickups/'})), '/pickups/')

    def test_registration_rejects_weak_password_and_invalid_email(self):
        for email, password in [('new@example.com', '123456'), ('not-an-email', 'LongComplexPassword!23')]:
            response = self.client.post('/register/', {'action': 'register', 'email': email, 'password': password, 'confirm_password': password})
            self.assertEqual(response.status_code, 200)
            self.assertFalse(CustomUser.objects.filter(email=email).exists())

    @override_settings(AUTH_REQUESTS_PER_MINUTE=2)
    def test_auth_requests_are_limited(self):
        self.client.post('/login/', {'email': 'none@example.com', 'password': 'invalid'})
        self.client.post('/login/', {'email': 'none@example.com', 'password': 'invalid'})
        self.assertEqual(self.client.post('/login/').status_code, 429)

    def test_fake_image_cannot_reach_upload_handler(self):
        response = self.client.post('/register/', {'avatar': SimpleUploadedFile('photo.jpg', b'<script>alert(1)</script>', content_type='image/jpeg')})
        self.assertEqual(response.status_code, 400)

    def test_image_is_reencoded_without_original_payload(self):
        data = BytesIO()
        Image.new('RGB', (10, 10)).save(data, 'PNG')
        cleaned = clean_image(SimpleUploadedFile('photo.png', data.getvalue() + b'<script>evil</script>'))
        self.assertEqual(cleaned.content_type, 'image/jpeg')
        self.assertNotIn(b'<script>', cleaned.read())

    def test_autocomplete_never_calls_public_geocoder(self):
        with patch('apps.books.web_views.search_osm_locations') as geocoder:
            self.assertEqual(self.client.get('/api/locations/suggest/?q=Dhaka').status_code, 200)
            geocoder.assert_not_called()

    def test_seller_edit_cannot_modify_another_sellers_catalog(self):
        from apps.books.models import Book
        from apps.listings.models import BookListing
        seller = CustomUser.objects.create_user(email='first@security.test')
        other = CustomUser.objects.create_user(email='second@security.test')
        book = Book.objects.create(title='Shared original')
        listing = BookListing.objects.create(book=book, seller=seller, price=100)
        BookListing.objects.create(book=book, seller=other, price=120)
        self.client.force_login(seller)
        response = self.client.post(f'/seller/listings/{listing.pk}/edit/', {'title': 'Malicious replacement', 'author': 'Changed author', 'price': '110', 'condition': 'GOOD', 'district': 'Dhaka', 'area': 'Mirpur', 'status': 'ACTIVE'})
        self.assertEqual(response.status_code, 302)
        book.refresh_from_db()
        listing.refresh_from_db()
        self.assertEqual(book.title, 'Shared original')
        self.assertEqual(listing.price, 110)

    def test_rotated_refresh_token_is_revoked(self):
        from rest_framework_simplejwt.tokens import RefreshToken
        user = CustomUser.objects.create_user(email='token@security.test')
        token = str(RefreshToken.for_user(user))
        self.assertEqual(self.client.post('/api/v1/accounts/token/refresh/', {'refresh': token}).status_code, 200)
        self.assertEqual(self.client.post('/api/v1/accounts/token/refresh/', {'refresh': token}).status_code, 401)

    def test_profile_does_not_create_sample_address(self):
        from apps.accounts.models import Address
        user = CustomUser.objects.create_user(email='profile@security.test')
        self.client.force_login(user)
        self.assertEqual(self.client.get('/profile/').status_code, 200)
        self.assertFalse(Address.objects.filter(user=user).exists())

    def test_inbox_history_is_bounded_and_earlier_messages_accessible(self):
        from apps.books.models import Book
        from apps.listings.models import BookListing
        from apps.messaging.models import Conversation, InquiryMessage
        buyer = CustomUser.objects.create_user(email='history-buyer@security.test')
        seller = CustomUser.objects.create_user(email='history-seller@security.test')
        listing = BookListing.objects.create(book=Book.objects.create(title='History book'), seller=seller, price=100)
        conversation = Conversation.objects.create(listing=listing, buyer=buyer, seller=seller)
        InquiryMessage.objects.bulk_create([InquiryMessage(conversation=conversation, sender=seller, text=str(i)) for i in range(201)])
        self.client.force_login(buyer)
        response = self.client.get('/inbox/', {'conv': conversation.pk})
        self.assertEqual(len(response.context['active_chat_messages']), 200)
        before = response.context['history_previous_id']
        older = self.client.get('/inbox/', {'conv': conversation.pk, 'before_id': before})
        self.assertEqual(len(older.context['active_chat_messages']), 1)
        self.assertEqual(older.context['active_chat_messages'][0].text, '0')

    def test_edit_invalid_original_price_does_not_save(self):
        from apps.books.models import Book
        from apps.listings.models import BookListing
        seller = CustomUser.objects.create_user(email='price@security.test')
        listing = BookListing.objects.create(book=Book.objects.create(title='Validated copy'), seller=seller, price=100)
        self.client.force_login(seller)
        self.client.post(f'/seller/listings/{listing.pk}/edit/', {'status':'ACTIVE','price':'110','original_mrp':'NaN','condition':'GOOD','district':'Dhaka','area':'Mirpur'})
        listing.refresh_from_db()
        self.assertEqual(listing.price, 100)

    def test_invalid_chat_api_payload_returns_validation_error(self):
        from rest_framework.test import APIClient
        user = CustomUser.objects.create_user(email='bad-payload@security.test')
        client = APIClient()
        client.force_authenticate(user)
        response = client.post('/api/v1/messaging/conversations/', {'listing_id':'invalid', 'message':{}}, format='json')
        self.assertEqual(response.status_code, 400)

    def test_buyer_overview_counts_only_own_purchases(self):
        from apps.books.models import Book
        from apps.listings.models import BookListing
        from apps.messaging.models import Conversation
        from apps.orders.models import PurchaseAgreement
        buyer = CustomUser.objects.create_user(email='overview-buyer@security.test')
        seller = CustomUser.objects.create_user(email='overview-seller@security.test')
        other = CustomUser.objects.create_user(email='overview-other@security.test')
        listing = BookListing.objects.create(book=Book.objects.create(title='Overview book'), seller=seller, price=100)
        for person in (buyer, other):
            conversation = Conversation.objects.create(listing=listing, buyer=person, seller=seller)
            PurchaseAgreement.objects.create(listing=listing, conversation=conversation, buyer=person, seller=seller, offered_price=100, status='COMPLETED')
        self.client.force_login(buyer)
        response = self.client.get('/profile/')
        self.assertEqual(response.context['active_tab'], 'overview')
        self.assertEqual(response.context['buyer_overview']['purchases'], 1)
        self.assertContains(response, 'Buyer Overview')
