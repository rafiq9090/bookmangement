from django import forms
from django.contrib import messages
from django.contrib.auth.models import Group
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.paginator import Paginator
from django.db import transaction, IntegrityError
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from .admin_roles import ROLE_PERMISSIONS
from .models import CustomUser, AdminActivity


class StaffForm(forms.Form):
    name = forms.CharField(max_length=150)
    email = forms.EmailField()
    password = forms.CharField(max_length=128, widget=forms.PasswordInput)
    roles = forms.MultipleChoiceField(choices=[(r, r) for r in ROLE_PERMISSIONS], widget=forms.CheckboxSelectMultiple)

    def clean_email(self):
        email = self.cleaned_data['email'].lower()
        if CustomUser.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError('An account with this email already exists.')
        return email

    def clean(self):
        data = super().clean()
        if data.get('password'):
            user = CustomUser(email=data.get('email', ''), first_name=data.get('name', ''))
            try:
                validate_password(data['password'], user)
            except ValidationError as error:
                self.add_error('password', error)
        return data


def manage_staff(request, tabs):
    if not request.user.is_superuser:
        raise PermissionDenied
    form = StaffForm(request.POST if request.method == 'POST' and request.POST.get('action') == 'create_staff' else None)
    if request.method == 'POST':
        action = request.POST.get('action')
        try:
            with transaction.atomic():
                if action == 'create_staff':
                    if form.is_valid():
                        data = form.cleaned_data
                        user = CustomUser.objects.create_user(email=data['email'], password=data['password'], first_name=data['name'], is_staff=True)
                        user.groups.set(Group.objects.filter(name__in=data['roles']))
                        AdminActivity.objects.create(actor=request.user, action=action, target=f'user:{user.pk}', reason='Staff account created', after={'roles': data['roles']})
                        messages.success(request, 'Staff account created.')
                        return redirect('/admin/dashboard/?tab=staff')
                elif action == 'update_staff':
                    user = get_object_or_404(CustomUser.objects.select_for_update(), pk=request.POST.get('pk'), is_staff=True)
                    if user.is_superuser or user.pk == request.user.pk:
                        raise ValidationError('Owner accounts cannot be changed here.')
                    roles = request.POST.getlist('roles')
                    if not roles or any(role not in ROLE_PERMISSIONS for role in roles):
                        raise ValidationError('Choose at least one valid role.')
                    reason = request.POST.get('reason', '').strip()
                    if not reason or len(reason) > 2000:
                        raise ValidationError('Enter a reason within 2,000 characters.')
                    before = {'roles': list(user.groups.values_list('name', flat=True)), 'active': user.is_active}
                    user.groups.set(Group.objects.filter(name__in=roles))
                    user.user_permissions.clear()
                    user.is_active = request.POST.get('active') == 'yes'
                    user.save(update_fields=['is_active'])
                    AdminActivity.objects.create(actor=request.user, action=action, target=f'user:{user.pk}', reason=reason, before=before, after={'roles': roles, 'active': user.is_active})
                    messages.success(request, 'Staff access updated.')
                    return redirect('/admin/dashboard/?tab=staff')
                else:
                    raise ValidationError('Unknown staff action.')
        except IntegrityError:
            form.add_error('email', 'An account with this email already exists. Please try another email.')
        except ValidationError as error:
            messages.error(request, '; '.join(error.messages))
    query = request.GET.get('q', '').strip()[:200]
    users = CustomUser.objects.filter(is_staff=True).prefetch_related('groups').order_by('-date_joined')
    if query:
        users = users.filter(Q(email__icontains=query) | Q(first_name__icontains=query))
    page = Paginator(users, 25).get_page(request.GET.get('page'))
    staff = [{'user': user, 'roles': list(user.groups.values_list('name', flat=True))} for user in page]
    return render(request, 'admin/staff_management.html', {'active_tab': 'staff', 'admin_tabs': tabs, 'form': form, 'staff': staff, 'roles': ROLE_PERMISSIONS, 'page_obj': page, 'query': query})
