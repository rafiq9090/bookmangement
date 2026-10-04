from django.core.management.base import BaseCommand
from django.contrib.auth.models import Group, Permission
from apps.accounts.admin_roles import ROLE_PERMISSIONS


class Command(BaseCommand):
    help = "Configure marketplace staff roles."

    def handle(self, *args, **kwargs):
        for name, codes in ROLE_PERMISSIONS.items():
            group, _ = Group.objects.get_or_create(name=name)
            permissions = []
            for code in codes:
                app, codename = code.split(".", 1)
                permissions.append(Permission.objects.get(content_type__app_label=app, codename=codename))
            group.permissions.set(permissions)
        self.stdout.write("Admin roles configured.")
