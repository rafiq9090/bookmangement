from django.test import TestCase
from django.core.management import call_command
from django.contrib.auth.models import Group
from .models import CustomUser, AdminActivity


class StaffManagementTests(TestCase):
    def setUp(self):
        call_command('setup_admin_roles', verbosity=0)
        self.owner = CustomUser.objects.create_superuser(email='owner@example.com', password='StrongTest123!')
        self.client.force_login(self.owner)

    def test_create_and_role_access(self):
        response = self.client.post('/admin/dashboard/?tab=staff', {'action': 'create_staff', 'name': 'Support', 'email': 'support@example.com', 'password': 'Violet!7392Book', 'roles': ['Support Agent']})
        self.assertEqual(response.status_code, 302)
        staff = CustomUser.objects.get(email='support@example.com')
        self.assertTrue(staff.check_password('Violet!7392Book'))
        self.assertTrue(staff.is_staff)
        self.assertFalse(staff.is_superuser)
        self.client.force_login(staff)
        self.assertEqual(self.client.get('/admin/dashboard/?tab=contact').status_code, 200)
        for tab in ['staff', 'listings', 'users', 'catalog', 'pickups']:
            self.assertEqual(self.client.get('/admin/dashboard/?tab='+tab).status_code, 403)
        self.assertEqual(self.client.post('/admin/dashboard/?tab=staff', {'action': 'create_staff'}).status_code, 403)

    def test_validation_and_owner_protected(self):
        data = {'action': 'create_staff', 'name': 'Reader', 'email': 'reader@example.com', 'password': '123', 'roles': ['Support Agent']}
        self.assertEqual(self.client.post('/admin/dashboard/?tab=staff', data).status_code, 200)
        self.assertFalse(CustomUser.objects.filter(email=data['email']).exists())
        self.client.post('/admin/dashboard/?tab=staff', {'action': 'update_staff', 'pk': self.owner.pk, 'roles': ['Support Agent'], 'reason': 'Test'})
        self.owner.refresh_from_db()
        self.assertTrue(self.owner.is_active)

    def test_role_change_and_disable_audited(self):
        staff = CustomUser.objects.create_user(email='staff@example.com', password='StrongTest123!', is_staff=True)
        staff.groups.add(Group.objects.get(name='Support Agent'))
        self.assertEqual(self.client.get('/admin/dashboard/?tab=staff').status_code, 200)
        self.client.post('/admin/dashboard/?tab=staff', {'action': 'update_staff', 'pk': staff.pk, 'roles': ['Catalog Editor'], 'reason': 'New responsibility', 'active': 'yes'})
        staff.refresh_from_db()
        self.assertEqual(list(staff.groups.values_list('name', flat=True)), ['Catalog Editor'])
        self.client.force_login(staff)
        self.assertEqual(self.client.get('/admin/dashboard/?tab=catalog').status_code, 200)
        self.assertEqual(self.client.get('/admin/dashboard/?tab=contact').status_code, 403)
        self.client.force_login(self.owner)
        self.client.post('/admin/dashboard/?tab=staff', {'action': 'update_staff', 'pk': staff.pk, 'roles': ['Catalog Editor'], 'reason': 'Disable access'})
        staff.refresh_from_db()
        self.assertFalse(staff.is_active)
        self.assertEqual(AdminActivity.objects.filter(action='update_staff').count(), 2)
