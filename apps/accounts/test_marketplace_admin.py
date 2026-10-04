from decimal import Decimal
from django.test import TestCase
from apps.accounts.models import CustomUser, AdminActivity
from apps.books.models import Book, Category
from apps.listings.models import BookListing


class MarketplaceAdminTests(TestCase):
    def setUp(self):
        self.admin = CustomUser.objects.create_superuser(email="ops@example.com", password="StrongPassword123!")
        self.buyer = CustomUser.objects.create_user(email="reader@example.com", password="StrongPassword123!")
        self.client.force_login(self.admin)
        book = Book.objects.create(title="Admin test book")
        self.listing = BookListing.objects.create(book=book, seller=self.buyer, price=Decimal("100"), status="ACTIVE", condition="GOOD")

    def post(self, action, pk=None, **extra):
        return self.client.post("/admin/dashboard/?tab=listings", {"action": action, "pk": pk or self.listing.pk, "reason": "Moderation review", "confirm": "yes", **extra})

    def test_tabs_render_and_legacy_finances_removed(self):
        for tab in ["overview", "listings", "users", "pickups", "reports", "catalog", "activity"]:
            response = self.client.get("/admin/dashboard/", {"tab": tab})
            self.assertEqual(response.status_code, 200, tab)
            self.assertNotContains(response, "Escrow Custody")
            self.assertNotContains(response, "Payout Batches")

    def test_hide_and_restore_audited(self):
        self.assertEqual(self.post("hide_listing").status_code, 302)
        self.listing.refresh_from_db();self.assertTrue(self.listing.is_deleted)
        self.assertEqual(AdminActivity.objects.get().before, {"is_deleted": False})
        self.post("restore_listing")
        self.listing.refresh_from_db();self.assertFalse(self.listing.is_deleted)
        self.assertEqual(AdminActivity.objects.count(), 2)

    def test_staff_without_permission_cannot_change(self):
        staff = CustomUser.objects.create_user(email="staff@example.com", password="StrongPassword123!", is_staff=True)
        self.client.force_login(staff)
        self.assertEqual(self.post("hide_listing").status_code, 403)
        self.assertFalse(AdminActivity.objects.exists())

    def test_sold_listing_protected(self):
        self.listing.status = "SOLD";self.listing.save()
        self.post("hide_listing")
        self.listing.refresh_from_db();self.assertFalse(self.listing.is_deleted)
        self.assertFalse(AdminActivity.objects.exists())

    def test_confirmation_and_reason_required(self):
        self.post("hide_listing", confirm="")
        self.post("hide_listing", reason="")
        self.assertFalse(AdminActivity.objects.exists())

    def test_admin_account_cannot_be_suspended(self):
        self.post("suspend_user", pk=self.admin.pk)
        self.admin.refresh_from_db();self.assertTrue(self.admin.is_active)

    def test_nonstaff_cannot_open_console(self):
        self.client.force_login(self.buyer)
        self.assertEqual(self.client.get("/admin/dashboard/").status_code, 302)

    def test_catalog_add_and_duplicate_rejected(self):
        self.post("save_category", pk="", name="New Genre")
        # Explicit empty primary key selects the creation workflow.
        response = self.client.post("/admin/dashboard/?tab=catalog", {"action": "save_category", "name": "Added Genre", "reason": "Improve catalog"})
        self.assertEqual(response.status_code, 302)
        self.assertTrue(Category.objects.filter(name="Added Genre").exists())
        self.client.post("/admin/dashboard/?tab=catalog", {"action": "save_category", "name": "Added Genre", "reason": "Duplicate"})
        self.assertEqual(Category.objects.filter(name="Added Genre").count(), 1)
