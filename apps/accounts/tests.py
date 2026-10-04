from django.test import TestCase
from rest_framework.test import APIClient
from apps.accounts.models import CustomUser, SellerProfile


class AccountsTestCase(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = CustomUser.objects.create_user(
            email="buyer@book.com",
            password="Rafiq@123",
            first_name="Rafiqul",
            last_name="Islam",
        )

    def test_user_registration(self):
        response = self.client.post(
            "/api/v1/accounts/register/",
            {
                "email": "newbuyer@example.com",
                "password": "ValidPassword123!",
                "first_name": "Zubair",
                "last_name": "Hossain",
            },
            format="json",
        )
        self.assertEqual(response.status_code, 201)
        self.assertIn("tokens", response.data)
        self.assertIn("access", response.data["tokens"])

    def test_seller_application(self):
        self.client.force_authenticate(user=self.user)
        response = self.client.post(
            "/api/v1/accounts/seller/apply/",
            {
                "store_name": "Vintage Treasures BD",
                "national_id_number": "1992019283719",
                "payout_method": "BKASH",
                "payout_account_details": "01711111111",
                "bio": "Rare 20th-century classics.",
            },
            format="json",
        )
        self.assertEqual(response.status_code, 201)
        self.user.refresh_from_db()
        self.assertTrue(self.user.is_seller)
        self.assertEqual(self.user.seller_profile.kyc_status, SellerProfile.KycStatus.PENDING)


class PickupSellerOnboardingTests(TestCase):
    def setUp(self):
        self.user = CustomUser.objects.create_user(email="pickup-seller@example.com", password="StrongPass123!")
        self.client.force_login(self.user)

    def test_can_become_seller_without_payout_or_identity(self):
        response = self.client.post("/seller/apply/", {"store_name": "Local Books", "bio": "Used books", "seller_agreement": "yes"})
        self.assertRedirects(response, "/seller/listings/", fetch_redirect_response=False)
        self.user.refresh_from_db()
        self.assertTrue(self.user.is_seller)
        profile = SellerProfile.objects.get(user=self.user)
        self.assertEqual(profile.payout_account_details, "")
        self.assertEqual(profile.national_id_number, "")

    def test_agreement_required_and_input_preserved(self):
        response = self.client.post("/seller/apply/", {"store_name": "My Books", "bio": "My bio"})
        self.assertEqual(response.status_code, 200)
        self.assertFalse(SellerProfile.objects.filter(user=self.user).exists())
        self.assertContains(response, 'value="My Books"')
        self.assertContains(response, "My bio")

    def test_edit_keeps_existing_private_details(self):
        profile = SellerProfile.objects.create(user=self.user, store_name="Old Name", national_id_number="existing-id", payout_account_details="existing-account", kyc_status="VERIFIED")
        self.client.post("/seller/apply/", {"store_name": "New Name", "seller_agreement": "yes"})
        profile.refresh_from_db()
        self.assertEqual(profile.national_id_number, "existing-id")
        self.assertEqual(profile.payout_account_details, "existing-account")
        self.assertEqual(profile.kyc_status, "VERIFIED")
