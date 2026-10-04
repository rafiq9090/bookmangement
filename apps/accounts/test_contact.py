from django.test import TestCase, Client
from .models import ContactMessage, CustomUser, AdminActivity


class ContactTests(TestCase):
    def setUp(self):
        from django.core.cache import cache
        cache.clear()

    def test_submission_validation_and_dashboard(self):
        self.assertEqual(self.client.get('/contact/').status_code, 200)
        self.client.post('/contact/', {'name': 'Reader', 'email': 'invalid'})
        self.assertFalse(ContactMessage.objects.exists())
        data = {'name': 'Reader', 'email': 'reader@example.com', 'subject': 'Help', 'message': '<script>alert(1)</script>'}
        self.assertEqual(self.client.post('/contact/', data).status_code, 302)
        self.client.post('/contact/', data)
        self.assertEqual(ContactMessage.objects.count(), 1)
        self.assertEqual(self.client.get('/admin/dashboard/?tab=contact').status_code, 302)
        admin = CustomUser.objects.create_superuser(email='contact-admin@example.com', password='TestPass123!')
        self.client.force_login(admin)
        response = self.client.get('/admin/dashboard/?tab=contact')
        self.assertContains(response, 'reader@example.com')
        self.assertContains(response, '&lt;script&gt;')
        obj = ContactMessage.objects.get()
        self.client.post('/admin/dashboard/?tab=contact', {'action': 'resolve_contact', 'pk': obj.pk, 'reason': 'Handled', 'confirm': 'yes'})
        obj.refresh_from_db()
        self.assertTrue(obj.resolved)
        self.assertTrue(AdminActivity.objects.filter(action='resolve_contact').exists())

    def test_staff_permissions_and_csrf(self):
        staff = CustomUser.objects.create_user(email='contact-staff@example.com', password='TestPass123!', is_staff=True)
        self.client.force_login(staff)
        self.assertEqual(self.client.get('/admin/dashboard/?tab=contact').status_code, 403)
        self.assertEqual(Client(enforce_csrf_checks=True).post('/contact/', {}).status_code, 403)
