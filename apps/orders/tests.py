from decimal import Decimal
from django.test import TestCase
from rest_framework.test import APIClient
from apps.accounts.models import CustomUser, SellerProfile
from apps.books.models import Book
from apps.listings.models import BookListing
from apps.orders.models import Cart, CartItem, Order, OrderShipment
from apps.orders.services.checkout import process_cart_checkout


class MultiVendorCheckoutTestCase(TestCase):
    def setUp(self):
        self.buyer = CustomUser.objects.create_user(
            email="buyer@test.com",
            password="Password123!",
        )
        self.seller_a = CustomUser.objects.create_user(
            email="seller_a@test.com",
            password="Password123!",
            is_seller=True,
        )
        SellerProfile.objects.create(user=self.seller_a, store_name="Dhaka Bookhouse")

        self.seller_b = CustomUser.objects.create_user(
            email="seller_b@test.com",
            password="Password123!",
            is_seller=True,
        )
        SellerProfile.objects.create(user=self.seller_b, store_name="Chittagong Vintage")

        book_1 = Book.objects.create(title="Book 1", isbn_13="9780000000001")
        book_2 = Book.objects.create(title="Book 2", isbn_13="9780000000002")

        self.listing_a = BookListing.objects.create(
            book=book_1,
            seller=self.seller_a,
            price=Decimal("100.00"),
            condition=BookListing.Condition.VERY_GOOD,
        )
        self.listing_b = BookListing.objects.create(
            book=book_2,
            seller=self.seller_b,
            price=Decimal("200.00"),
            condition=BookListing.Condition.LIKE_NEW,
        )

    def test_multi_vendor_shipment_split(self):
        cart = Cart.objects.create(user=self.buyer)
        CartItem.objects.create(cart=cart, listing=self.listing_a)
        CartItem.objects.create(cart=cart, listing=self.listing_b)

        shipping_info = {
            "recipient_name": "Test Buyer",
            "phone_number": "01800000000",
            "street_address": "House 1, Road 2",
            "city": "Dhaka",
            "state_division": "Dhaka",
            "postal_code": "1205",
            "country": "Bangladesh",
        }

        order = process_cart_checkout(buyer=self.buyer, shipping_address_data=shipping_info)

        self.assertEqual(order.status, Order.Status.PENDING)
        # 2 sellers -> 2 shipments
        self.assertEqual(order.shipments.count(), 2)
        
        # ৳100 + ৳200 + (2 shipments * ৳60) = ৳420
        self.assertEqual(order.total_amount, Decimal("420.00"))
        self.assertEqual(order.shipping_total, Decimal("120.00"))

        # Check escrow creation
        self.assertEqual(order.escrow_holds.count(), 2)

        # Ensure cart is emptied
        self.assertEqual(cart.items.count(), 0)
