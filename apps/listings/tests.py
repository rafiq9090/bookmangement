from decimal import Decimal
from django.test import TestCase
from rest_framework.test import APIClient
from apps.accounts.models import CustomUser
from apps.books.models import Book
from apps.listings.models import BookListing


class ListingsTestCase(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.seller = CustomUser.objects.create_user(
            email="seller@example.com",
            password="StrongPassword123!",
            is_seller=True,
        )
        self.book = Book.objects.create(
            title="The Old Man and the Sea",
            isbn_13="9780684801223",
            publication_year=1952,
        )

    def test_seller_creates_used_book_listing(self):
        self.client.force_authenticate(user=self.seller)
        response = self.client.post(
            "/api/v1/listings/",
            {
                "book": self.book.id,
                "district": "Dhaka", "area": "Mirpur",
                "condition": BookListing.Condition.LIKE_NEW,
                "condition_notes": "First edition reprint, minor shelf dust on jacket.",
                "price": "45.00",
                "edition_year": 1960,
                "is_hardcover": True,
            },
            format="json",
        )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(BookListing.objects.count(), 1)
        listing = BookListing.objects.first()
        self.assertEqual(listing.price, Decimal("45.00"))
        self.assertEqual(listing.status, BookListing.Status.DRAFT)

    def test_regular_user_can_create_listing(self):
        regular_user = CustomUser.objects.create_user(
            email="regular@example.com",
            password="StrongPassword123!",
            is_seller=False,
        )
        self.client.force_authenticate(user=regular_user)
        response = self.client.post(
            "/api/v1/listings/",
            {
                "book": self.book.id,
                "district": "Dhaka", "area": "Mirpur",
                "condition": BookListing.Condition.GOOD,
                "price": "20.00",
            },
            format="json",
        )
        self.assertEqual(response.status_code, 201)
        regular_user.refresh_from_db()
        self.assertTrue(regular_user.is_seller)


class ManualSoldTests(TestCase):
    def setUp(self):
        self.seller = CustomUser.objects.create_user(email="manual-seller@example.com", password="pass12345")
        self.other = CustomUser.objects.create_user(email="manual-other@example.com", password="pass12345")
        self.book = Book.objects.create(title="Manual sale", slug="manual-sale")
        self.listing = BookListing.objects.create(book=self.book, seller=self.seller, price="100.00", condition="GOOD")
        self.url = f"/seller/listings/{self.listing.pk}/sold/"
        self.client.force_login(self.seller)

    def test_seller_marks_sold_and_removes_cart(self):
        from apps.orders.models import Cart, CartItem
        CartItem.objects.create(cart=Cart.objects.create(user=self.other), listing=self.listing)
        self.assertEqual(self.client.post(self.url).status_code, 302)
        self.listing.refresh_from_db()
        self.assertEqual(self.listing.status, "SOLD")
        self.assertFalse(self.listing.cart_items.exists())
        self.assertEqual(self.client.post(self.url).status_code, 302)

    def test_other_seller_cannot_change_listing(self):
        self.client.force_login(self.other)
        self.assertEqual(self.client.post(self.url).status_code, 404)
        self.listing.refresh_from_db()
        self.assertEqual(self.listing.status, "ACTIVE")

    def test_get_does_not_change_inventory(self):
        self.assertEqual(self.client.get(self.url).status_code, 405)
        self.listing.refresh_from_db()
        self.assertEqual(self.listing.status, "ACTIVE")

    def test_live_pickup_cannot_be_bypassed(self):
        from apps.messaging.models import Conversation
        from apps.orders.models import PurchaseAgreement
        conversation = Conversation.objects.create(buyer=self.other, seller=self.seller, listing=self.listing)
        PurchaseAgreement.objects.create(conversation=conversation, listing=self.listing, buyer=self.other, seller=self.seller, offered_price="100.00", status="RESERVED")
        self.listing.status = "RESERVED"
        self.listing.save()
        self.assertEqual(self.client.post(self.url).status_code, 302)
        self.listing.refresh_from_db()
        self.assertEqual(self.listing.status, "RESERVED")

    def test_confirmed_manual_sale_cancels_reservation(self):
        from apps.messaging.models import Conversation
        from apps.orders.models import PurchaseAgreement
        conversation = Conversation.objects.create(buyer=self.other, seller=self.seller, listing=self.listing)
        agreement = PurchaseAgreement.objects.create(conversation=conversation, listing=self.listing, buyer=self.other, seller=self.seller, offered_price="100.00", accepted_price="100.00", status="RESERVED")
        self.listing.status = "RESERVED"
        self.listing.save()
        self.client.post(self.url, {"cancel_reservation": "yes"})
        self.listing.refresh_from_db()
        agreement.refresh_from_db()
        self.assertEqual(self.listing.status, "SOLD")
        self.assertEqual(agreement.status, "CANCELLED")

    def test_edit_manual_sold_listing_can_reactivate(self):
        self.listing.status = "SOLD"
        self.listing.save()
        response = self.client.post(f"/seller/listings/{self.listing.pk}/edit/", {"status": "ACTIVE", "price": "125.00", "condition": "GOOD", "district": "Dhaka", "area": "Mirpur"})
        self.assertEqual(response.status_code, 302)
        self.listing.refresh_from_db()
        self.assertEqual(self.listing.status, "ACTIVE")
        self.assertEqual(self.listing.price, Decimal("125.00"))

    def test_edit_can_mark_available_copy_sold(self):
        self.client.post(f"/seller/listings/{self.listing.pk}/edit/", {"status": "SOLD", "price": "100.00", "condition": "GOOD", "district": "Dhaka", "area": "Mirpur"})
        self.listing.refresh_from_db()
        self.assertEqual(self.listing.status, "SOLD")

    def test_edit_reserved_copy_changes_status_with_confirmation(self):
        from apps.messaging.models import Conversation
        from apps.orders.models import PurchaseAgreement
        conversation = Conversation.objects.create(buyer=self.other, seller=self.seller, listing=self.listing)
        agreement = PurchaseAgreement.objects.create(conversation=conversation, listing=self.listing, buyer=self.other, seller=self.seller, offered_price="100.00", accepted_price="100.00", status="RESERVED")
        self.listing.status = "RESERVED"
        self.listing.save()
        data = {"status": "ACTIVE", "price": "100.00", "condition": "GOOD", "district": "Dhaka", "area": "Mirpur"}
        self.client.post(f"/seller/listings/{self.listing.pk}/edit/", data)
        self.listing.refresh_from_db()
        self.assertEqual(self.listing.status, "RESERVED")
        data["cancel_reservation"] = "yes"
        self.client.post(f"/seller/listings/{self.listing.pk}/edit/", data)
        self.listing.refresh_from_db()
        agreement.refresh_from_db()
        self.assertEqual(self.listing.status, "ACTIVE")
        self.assertEqual(agreement.status, "CANCELLED")
