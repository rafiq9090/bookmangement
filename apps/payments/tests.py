from decimal import Decimal
from django.test import TestCase
from apps.accounts.models import CustomUser, SellerProfile
from apps.books.models import Book
from apps.listings.models import BookListing
from apps.orders.models import Order, OrderItem, OrderShipment
from apps.payments.models import EscrowHold, Payment, SellerLedger
from apps.payments.services.ledger import (
    confirm_payment_and_finalize_order,
    release_escrow_to_seller,
)


class PaymentsAndEscrowTestCase(TestCase):
    def setUp(self):
        self.buyer = CustomUser.objects.create_user(email="buyer@test.com", password="Pass123!")
        self.seller = CustomUser.objects.create_user(email="seller@test.com", password="Pass123!", is_seller=True)
        SellerProfile.objects.create(user=self.seller, store_name="Rare Book Depot")

        book = Book.objects.create(title="Vintage Book", isbn_13="9781234567890")
        self.listing = BookListing.objects.create(
            book=book,
            seller=self.seller,
            price=Decimal("1000.00"),
            status=BookListing.Status.RESERVED,
        )

        self.order = Order.objects.create(
            buyer=self.buyer,
            total_amount=Decimal("1060.00"),
            shipping_total=Decimal("60.00"),
            status=Order.Status.PENDING,
        )

        self.shipment = OrderShipment.objects.create(
            order=self.order,
            seller=self.seller,
            shipping_fee=Decimal("60.00"),
            subtotal=Decimal("1000.00"),
            status=OrderShipment.ShipmentStatus.WAITING_SELLER,
        )
        OrderItem.objects.create(
            shipment=self.shipment,
            listing=self.listing,
            price_at_purchase=Decimal("1000.00"),
        )

        self.escrow = EscrowHold.objects.create(
            order=self.order,
            shipment=self.shipment,
            gross_amount=Decimal("1000.00"),
            platform_fee=Decimal("150.00"),
            seller_net_amount=Decimal("850.00"),
            status=EscrowHold.EscrowStatus.HELD,
        )

    def test_confirm_payment_marks_inventory_sold(self):
        payment = confirm_payment_and_finalize_order(
            order=self.order,
            transaction_id="TXN-10293847",
        )
        self.assertEqual(payment.status, Payment.Status.SUCCESS)
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, Order.Status.PAID)
        self.listing.refresh_from_db()
        self.assertEqual(self.listing.status, BookListing.Status.SOLD)

    def test_escrow_release_credits_seller_ledger(self):
        self.shipment.status = OrderShipment.ShipmentStatus.DELIVERED
        self.shipment.save(update_fields=["status"])

        escrow = release_escrow_to_seller(self.shipment)
        self.assertEqual(escrow.status, EscrowHold.EscrowStatus.RELEASED)

        ledger_entry = SellerLedger.objects.filter(seller=self.seller).first()
        self.assertIsNotNone(ledger_entry)
        self.assertEqual(ledger_entry.amount, Decimal("850.00"))
        self.assertEqual(ledger_entry.entry_type, SellerLedger.EntryType.SALE_CREDIT)
