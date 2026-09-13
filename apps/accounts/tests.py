from django.test import TestCase
from rest_framework.test import APIClient
from apps.accounts.models import CustomUser, SellerProfile


class AccountsTestCase(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = CustomUser.objects.create_user(
            email="buyer@example.com",
            password="StrongPassword123!",
            first_name="Jane",
            last_name="Doe",
        )

    def test_user_registration(self):
        response = self.client.post(
            "/api/v1/accounts/register/",
            {
                "email": "newuser@example.com",
                "password": "Password12345!",
                "first_name": "John",
                "last_name": "Smith",
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
