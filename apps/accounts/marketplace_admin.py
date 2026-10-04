"""Custom local-pickup administration with permission-checked, audited actions."""
from django.contrib import messages
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.text import slugify
from rest_framework.exceptions import ValidationError as ServiceError
from apps.books.models import Book, Category, Author
from apps.listings.models import BookListing
from apps.orders.models import PurchaseAgreement, MarketplaceReport
from .models import CustomUser, SellerProfile, AdminActivity, PushDelivery, ContactMessage
from .admin_roles import can_access

TABS = [("overview", "Overview"), ("listings", "Listings"), ("users", "Users & Sellers"),
        ("pickups", "Pickups"), ("reports", "Reports"), ("catalog", "Categories & Authors"),
        ("contact", "Contact Messages"), ("activity", "Activity Log"), ("staff", "Admin Management")]


def permitted(user, permission):
    if not user.has_perm(permission):
        raise PermissionDenied("Your admin role cannot perform this action.")


@transaction.atomic
def apply_action(request):
    action = request.POST.get("action", "")
    if request.POST.get("confirm") != "yes" and action not in ("save_category", "save_author"):
        raise ValidationError("Confirm this action before submitting.")
    reason = request.POST.get("reason", "").strip()
    if not reason or len(reason) > 2000:
        raise ValidationError("Enter a reason of up to 2,000 characters.")
    pk = request.POST.get("pk")
    before, after = {}, {}
    if action in ("hide_listing", "restore_listing"):
        permitted(request.user, "listings.change_booklisting")
        obj = get_object_or_404(BookListing.objects.select_for_update(), pk=pk)
        if obj.status in ("SOLD", "RESERVED") or obj.agreements.filter(status__in=["RESERVED", "PICKUP_AGREED", "AWAITING_CONFIRMATION", "DISPUTED", "COMPLETED"]).exists():
            raise ValidationError("This copy has a protected transaction. Review its pickup first.")
        before = {"is_deleted": obj.is_deleted}
        obj.is_deleted = action == "hide_listing"
        obj.save(update_fields=["is_deleted"])
        after = {"is_deleted": obj.is_deleted}
        target = f"listing:{obj.pk}"
    elif action in ("suspend_user", "restore_user"):
        permitted(request.user, "accounts.change_customuser")
        obj = get_object_or_404(CustomUser.objects.select_for_update(), pk=pk)
        if obj.pk == request.user.pk or obj.is_staff or obj.is_superuser:
            raise ValidationError("Admin accounts cannot be suspended through this page.")
        before = {"is_active": obj.is_active}
        obj.is_active = action == "restore_user"
        obj.save(update_fields=["is_active"])
        after = {"is_active": obj.is_active}
        target = f"user:{obj.pk}"
    elif action in ("resolve_report", "dismiss_report"):
        permitted(request.user, "orders.change_marketplacereport")
        obj = get_object_or_404(MarketplaceReport.objects.select_for_update(), pk=pk)
        if obj.status != "PENDING":
            raise ValidationError("This report has already been reviewed.")
        before = {"status": obj.status}
        obj.status = "RESOLVED" if action == "resolve_report" else "DISMISSED"
        obj.resolution = reason
        obj.save(update_fields=["status", "resolution"])
        after = {"status": obj.status}
        target = f"report:{obj.pk}"
    elif action == "resolve_pickup":
        permitted(request.user, "orders.change_purchaseagreement")
        from apps.orders.services.pickup import resolve_dispute
        obj = get_object_or_404(PurchaseAgreement.objects.select_for_update(), pk=pk)
        before = {"status": obj.status}
        resolve_dispute(obj.pk, request.user, request.POST.get("outcome"), reason)
        obj.refresh_from_db()
        after = {"status": obj.status}
        target = f"pickup:{obj.pk}"
    elif action in ("resolve_contact", "reopen_contact"):
        permitted(request.user, "accounts.change_contactmessage")
        obj = get_object_or_404(ContactMessage.objects.select_for_update(), pk=pk)
        before = {"resolved": obj.resolved}
        obj.resolved = action == "resolve_contact"
        obj.save(update_fields=["resolved"])
        after = {"resolved": obj.resolved}
        target = f"contact:{obj.pk}"
    elif action in ("save_category", "save_author"):
        model = Category if action == "save_category" else Author
        label = model._meta.model_name
        permitted(request.user, f"books.{'change' if pk else 'add'}_{label}")
        name = request.POST.get("name", "").strip()
        if not name or len(name) > model._meta.get_field("name").max_length:
            raise ValidationError("Enter a valid name within the field limit.")
        if model.objects.filter(name__iexact=name).exclude(pk=pk or None).exists():
            raise ValidationError("An entry with this name already exists.")
        obj = get_object_or_404(model.objects.select_for_update(), pk=pk) if pk else model()
        before = {"name": obj.name} if pk else {}
        obj.name = name
        if not obj.slug:
            obj.slug = slugify(name) or f"{label}-{timezone.now().timestamp():.0f}"
        obj.full_clean()
        obj.save()
        after = {"name": obj.name}
        target = f"{label}:{obj.pk}"
    else:
        raise ValidationError("Unknown administrative action.")
    AdminActivity.objects.create(actor=request.user, action=action, target=target, reason=reason, before=before, after=after)


def dashboard(request):
    if not request.user.is_authenticated or not request.user.is_active or not request.user.is_staff:
        return redirect("/admin-login/?next=/admin/dashboard/")
    tab = request.GET.get("tab", "overview")
    if tab not in dict(TABS): tab = "overview"
    if not can_access(request.user, tab):
        raise PermissionDenied("Your role cannot access this section.")
    if tab == "staff":
        from .staff_management import manage_staff
        return manage_staff(request, [(key, name) for key, name in TABS if can_access(request.user, key)])
    if request.method == "POST":
        try:
            apply_action(request)
            messages.success(request, "Change saved and recorded in the activity log.")
        except (ValidationError, ServiceError, ValueError, TypeError) as error:
            messages.error(request, str(error))
        return redirect(f"/admin/dashboard/?tab={tab}")
    q = request.GET.get("q", "").strip()[:200]
    status = request.GET.get("status", "")
    kind = request.GET.get("kind", "category")
    rows, choices = [], []
    if tab == "listings":
        items = BookListing.objects.select_related("book", "seller").prefetch_related("images").order_by("-created_at")
        if q: items = items.filter(Q(book__title__icontains=q) | Q(book__isbn_13__icontains=q) | Q(seller__email__icontains=q))
        choices = [("hidden", "Hidden")] + list(BookListing.Status.choices)
        if status == "hidden": items = items.filter(is_deleted=True)
        elif status: items = items.filter(status=status, is_deleted=False)
    elif tab == "users":
        items = CustomUser.objects.order_by("-date_joined")
        if q: items = items.filter(Q(email__icontains=q) | Q(first_name__icontains=q) | Q(last_name__icontains=q))
        choices = [("active", "Active"), ("suspended", "Suspended"), ("seller", "Sellers")]
        if status == "active": items = items.filter(is_active=True)
        elif status == "suspended": items = items.filter(is_active=False)
        elif status == "seller": items = items.filter(is_seller=True)
    elif tab == "pickups":
        items = PurchaseAgreement.objects.select_related("listing__book", "buyer", "seller").order_by("-created_at")
        if q: items = items.filter(Q(listing__book__title__icontains=q) | Q(buyer__email__icontains=q) | Q(seller__email__icontains=q))
        choices = list(PurchaseAgreement.Status.choices)
        if status: items = items.filter(status=status)
    elif tab == "reports":
        items = MarketplaceReport.objects.select_related("listing__book", "reporter").order_by("-created_at")
        if q: items = items.filter(Q(details__icontains=q) | Q(listing__book__title__icontains=q))
        choices = list(MarketplaceReport.Status.choices)
        if status: items = items.filter(status=status)
    elif tab == "contact":
        permitted(request.user, "accounts.view_contactmessage")
        items = ContactMessage.objects.all()
        if q: items = items.filter(Q(name__icontains=q) | Q(email__icontains=q) | Q(subject__icontains=q) | Q(message__icontains=q))
        choices = [("new", "New"), ("resolved", "Resolved")]
        if status in ("new", "resolved"): items = items.filter(resolved=status == "resolved")
    elif tab == "catalog":
        kind = "author" if kind == "author" else "category"
        items = (Author if kind == "author" else Category).objects.order_by("name")
        if q: items = items.filter(name__icontains=q)
    elif tab == "activity":
        permitted(request.user, "accounts.view_adminactivity")
        items = AdminActivity.objects.select_related("actor").all()
        if q: items = items.filter(Q(target__icontains=q) | Q(reason__icontains=q) | Q(actor__email__icontains=q))
    else:
        items = MarketplaceReport.objects.none()
    page = Paginator(items, 25).get_page(request.GET.get("page"))
    for obj in page:
        row = {"pk": obj.pk, "actions": []}
        if tab == "listings":
            row.update(title=obj.book.title, detail=f"{obj.seller.email} · ৳{obj.price}", status="Hidden" if obj.is_deleted else obj.get_status_display())
            row.update(seller=obj.seller.email, price=obj.price, condition=obj.get_condition_display(), listed=obj.created_at, isbn=obj.book.isbn_13 or obj.book.isbn_10)
            image = next(iter(obj.images.all()), None)
            row.update(url=f"/books/{obj.book.slug}/", image=image.image.url if image else (obj.book.cover_image.url if obj.book.cover_image else ""))
            if request.user.has_perm("listings.change_booklisting") and obj.status not in ("SOLD", "RESERVED"):
                row["actions"] = [("restore_listing", "Restore listing")] if obj.is_deleted else [("hide_listing", "Hide listing")]
        elif tab == "users":
            row.update(title=obj.get_full_name() or obj.email, detail=obj.email, status=("Seller" if obj.is_seller else "Buyer") + (" · Active" if obj.is_active else " · Suspended"))
            if request.user.has_perm("accounts.change_customuser") and not obj.is_staff and not obj.is_superuser and obj.pk != request.user.pk:
                row["actions"] = [("suspend_user", "Suspend access")] if obj.is_active else [("restore_user", "Restore access")]
        elif tab == "pickups":
            row.update(title=obj.listing.book.title, detail=f"Buyer: {obj.buyer.email} · Seller: {obj.seller.email}", extra=obj.pickup_place, status=obj.get_status_display())
            if obj.status == "DISPUTED" and request.user.has_perm("orders.change_purchaseagreement"):
                row.update(actions=[("resolve_pickup", "Resolve dispute")], dispute=True, extra=obj.problem_details)
        elif tab == "reports":
            row.update(title=obj.listing.book.title, detail=obj.details, status=obj.get_status_display(), extra=obj.resolution)
            if obj.status == "PENDING" and request.user.has_perm("orders.change_marketplacereport"):
                row["actions"] = [("resolve_report", "Resolve report"), ("dismiss_report", "Dismiss report")]
        elif tab == "contact":
            row.update(title=obj.subject, detail=f"{obj.name} · {obj.email} · {obj.created_at:%d %b %Y %H:%M}", extra=obj.message, status="Resolved" if obj.resolved else "New")
            if request.user.has_perm("accounts.change_contactmessage"):
                row["actions"] = [("reopen_contact", "Reopen message")] if obj.resolved else [("resolve_contact", "Mark resolved")]
        elif tab == "catalog":
            row.update(title=obj.name, detail=f"{obj.books.count()} books", status=kind.title())
            if request.user.has_perm(f"books.change_{kind}"):
                row.update(actions=[(f"save_{kind}", "Save name")], catalog=True)
        elif tab == "activity":
            row.update(title=obj.action.replace("_", " ").title(), detail=f"{obj.actor.email if obj.actor else 'Deleted administrator'} · {obj.target}", extra=obj.reason, status=obj.created_at.strftime("%d %b %Y %H:%M"), changes={"before": obj.before, "after": obj.after})
        rows.append(row)
    metrics = [("Active listings", BookListing.objects.filter(status="ACTIVE", is_deleted=False, condition_needs_review=False).count()),
               ("Buyers", CustomUser.objects.filter(is_active=True, is_staff=False).count()),
               ("Sellers", CustomUser.objects.filter(is_seller=True, is_active=True).count()),
               ("Pending pickups", PurchaseAgreement.objects.exclude(status__in=["COMPLETED", "CANCELLED", "EXPIRED"]).count()),
               ("Completed handovers", PurchaseAgreement.objects.filter(status="COMPLETED").count()),
               ("Unresolved reports", MarketplaceReport.objects.filter(status="PENDING").count())]
    metric_tabs = ["listings", "users", "users", "pickups", "pickups", "reports"]
    metrics = [metric for metric, required_tab in zip(metrics, metric_tabs) if can_access(request.user, required_tab)]
    params = request.GET.copy(); params.pop("page", None)
    tabs = [(key, name) for key, name in TABS if can_access(request.user, key)]
    return render(request, "admin/marketplace_dashboard.html", {"active_tab": tab, "admin_tabs": tabs, "rows": rows, "page_obj": page,
        "query_params": params.urlencode(), "query": q, "status_filter": status, "status_choices": choices, "catalog_kind": kind,
        "can_add_catalog": request.user.has_perm(f"books.add_{kind}"), "metrics": metrics,
        "show_system_status": request.user.is_superuser,
        "pending_push": PushDelivery.objects.filter(sent_at__isnull=True).count() if request.user.is_superuser else None,
        "expired_reservations": PurchaseAgreement.objects.filter(status="RESERVED", reservation_expires_at__lt=timezone.now()).count() if request.user.is_superuser else None})
