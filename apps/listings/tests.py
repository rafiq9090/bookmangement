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
        self.assertEqual(listing.status, BookListing.Status.ACTIVE)

    def test_non_seller_cannot_create_listing(self):
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
                "condition": BookListing.Condition.GOOD,
                "price": "20.00",
            },
            format="json",
        )
        self.assertEqual(response.status_code, 403)
