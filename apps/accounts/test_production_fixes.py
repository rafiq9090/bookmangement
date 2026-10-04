from unittest.mock import patch
from django.test import TestCase, Client, override_settings
from django.core.cache import cache
from django.db import IntegrityError
from django.core.management import call_command
from .models import CustomUser, PushDelivery
from apps.books.models import Book
from apps.listings.models import BookListing
from apps.orders.models import MarketplaceReport
from .push_tasks import recover_pending_push


class ProductionFixTests(TestCase):
    def setUp(self):
        cache.clear()
        self.user = CustomUser.objects.create_user(email='fix@example.com', password='TestPassword123!')
        self.book = Book.objects.create(title='Audit book')
        self.listing = BookListing.objects.create(book=self.book, seller=self.user, price=100, original_mrp=120)

    def test_contact_quota_survives_new_sessions(self):
        data = {'name': 'Reader', 'email': 'reader@example.com', 'subject': 'Help', 'message': 'Question'}
        for _ in range(5):
            self.assertEqual(Client().post('/contact/', data).status_code, 302)
        self.assertEqual(Client().post('/contact/', data).status_code, 429)

    def test_submission_fails_closed_when_shared_cache_fails(self):
        with patch('apps.accounts.submission_limits.cache.add', side_effect=ConnectionError):
            self.assertEqual(self.client.post('/contact/', {}).status_code, 503)

    def test_support_overview_does_not_expose_other_role_metrics(self):
        from django.contrib.auth.models import Group
        call_command('setup_admin_roles', verbosity=0)
        self.user.is_staff = True
        self.user.save(update_fields=['is_staff'])
        self.user.groups.add(Group.objects.get(name='Support Agent'))
        self.client.force_login(self.user)
        response = self.client.get('/admin/dashboard/')
        self.assertNotContains(response, 'Active listings')
        self.assertNotContains(response, 'Pending pickups')
        self.assertNotContains(response, 'System status')

    def test_reports_validate_and_deduplicate(self):
        self.client.force_login(self.user)
        path = f'/listings/{self.listing.pk}/report/'
        self.client.post(path, {'details': 'x' * 4001})
        self.assertFalse(MarketplaceReport.objects.exists())
        self.client.post(path, {'details': 'Problem'})
        self.client.post(path, {'details': 'Problem again'})
        self.assertEqual(MarketplaceReport.objects.count(), 1)

    def test_book_copy_is_truthful(self):
        response = self.client.get(f'/books/{self.book.slug}/')
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, 'Save 50%')
        self.assertNotContains(response, 'eighteenth century London')

    @override_settings(WEB_PUSH_PRIVATE_KEY='configured')
    def test_pending_push_recovery(self):
        delivery = PushDelivery.objects.create(user=self.user, event_key='recovery', title='Update', url='/pickups/')
        with patch('apps.accounts.push_tasks.deliver_push.delay') as enqueue:
            self.assertEqual(recover_pending_push.run(), 1)
            enqueue.assert_called_once_with(delivery.pk)

    def test_concurrent_staff_email_conflict_is_handled(self):
        call_command('setup_admin_roles', verbosity=0)
        owner = CustomUser.objects.create_superuser(email='fix-owner@example.com', password='TestPassword123!')
        self.client.force_login(owner)
        with patch('apps.accounts.staff_management.CustomUser.objects.create_user', side_effect=IntegrityError):
            response = self.client.post('/admin/dashboard/?tab=staff', {'action': 'create_staff', 'email': 'new@example.com', 'name': 'Support', 'password': 'Violet7392!Book', 'roles': ['Support Agent']})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'already exists')
