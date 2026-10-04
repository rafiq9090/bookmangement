ROLE_PERMISSIONS = {
    "Marketplace Moderator": ["listings.view_booklisting", "listings.change_booklisting", "orders.view_marketplacereport", "orders.change_marketplacereport", "orders.view_purchaseagreement", "orders.change_purchaseagreement", "accounts.view_adminactivity"],
    "Catalog Editor": ["books.view_category", "books.add_category", "books.change_category", "books.view_author", "books.add_author", "books.change_author", "accounts.view_adminactivity"],
    "Account Manager": ["accounts.view_customuser", "accounts.change_customuser", "accounts.view_adminactivity"],
    "Support Agent": ["accounts.view_contactmessage", "accounts.change_contactmessage", "accounts.view_adminactivity"],
}

TAB_PERMISSIONS = {
    "listings": ["listings.view_booklisting", "listings.change_booklisting"],
    "users": ["accounts.view_customuser", "accounts.change_customuser"],
    "pickups": ["orders.view_purchaseagreement", "orders.change_purchaseagreement"],
    "reports": ["orders.view_marketplacereport", "orders.change_marketplacereport"],
    "catalog": ["books.view_category", "books.view_author", "books.add_category", "books.add_author", "books.change_category", "books.change_author"],
    "contact": ["accounts.view_contactmessage", "accounts.change_contactmessage"],
    "activity": ["accounts.view_adminactivity"],
}


def can_access(user, tab):
    if tab == "staff":
        return user.is_superuser
    if tab == "overview":
        return True
    return any(user.has_perm(p) for p in TAB_PERMISSIONS.get(tab, []))
