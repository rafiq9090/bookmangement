import re
from django.core import mail
from django.core.cache import cache
from django.test import TestCase, Client, override_settings
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode
from .models import CustomUser


@override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
class PasswordResetTests(TestCase):
    def setUp(self):
        cache.clear()
        self.user = CustomUser.objects.create_user(email='reset@example.com', password='OldPassword789!')

    def test_reset_email_password_change_and_single_use(self):
        self.assertContains(self.client.get('/login/'), 'href="/password-reset/"')
        self.assertContains(self.client.get('/password-reset/'), 'Send reset link')
        response = self.client.post('/password-reset/', {'email': self.user.email})
        self.assertRedirects(response, '/password-reset/done/')
        self.assertEqual(len(mail.outbox), 1)
        path = re.search(r'http://testserver(/reset/[^\s]+)', mail.outbox[0].body).group(1)
        response = self.client.get(path)
        confirm_path = response.url
        self.assertContains(self.client.get(confirm_path), 'Choose a new password')
        response = self.client.post(confirm_path, {'new_password1': 'NewViolet7392!Book', 'new_password2': 'NewViolet7392!Book'})
        self.assertRedirects(response, '/reset/done/')
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password('NewViolet7392!Book'))
        self.assertFalse(self.user.check_password('OldPassword789!'))
        self.assertContains(Client().get(path), 'This link is no longer valid')

    def test_unknown_account_returns_same_confirmation_without_email(self):
        response = self.client.post('/password-reset/', {'email': 'unknown@example.com'})
        self.assertRedirects(response, '/password-reset/done/')
        self.assertEqual(len(mail.outbox), 0)

    def test_invalid_token_and_csrf(self):
        uid = urlsafe_base64_encode(force_bytes(self.user.pk))
        self.assertContains(self.client.get(f'/reset/{uid}/invalid/'), 'This link is no longer valid')
        self.assertEqual(Client(enforce_csrf_checks=True).post('/password-reset/', {'email': self.user.email}).status_code, 403)

    def test_weak_and_mismatched_password_rejected(self):
        self.client.post('/password-reset/', {'email': self.user.email})
        path = re.search(r'http://testserver(/reset/[^\s]+)', mail.outbox[0].body).group(1)
        confirm = self.client.get(path).url
        self.assertEqual(self.client.post(confirm, {'new_password1': '123', 'new_password2': '123'}).status_code, 200)
        self.assertEqual(self.client.post(confirm, {'new_password1': 'NewViolet7392!Book', 'new_password2': 'DifferentPassword'}).status_code, 200)
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password('OldPassword789!'))
