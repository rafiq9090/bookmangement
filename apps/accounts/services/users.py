from django.db import transaction
from rest_framework.exceptions import ValidationError
from apps.accounts.models import CustomUser, SellerProfile


def apply_for_seller_account(
    user: CustomUser,
    store_name: str,
    national_id_number: str = "",
    payout_method: str = "BKASH",
    payout_account_details: str = "",
    bio: str = "",
) -> SellerProfile:
    """Enrolls an existing customer into seller status. KYC verification is optional."""
    if hasattr(user, "seller_profile"):
        raise ValidationError("This user already has a registered seller profile.")

    if SellerProfile.objects.filter(store_name__iexact=store_name).exists():
        raise ValidationError("Store name is already taken. Please choose another.")

    kyc_status = (
        SellerProfile.KycStatus.PENDING
        if national_id_number.strip()
        else SellerProfile.KycStatus.UNVERIFIED
    )

    with transaction.atomic():
        profile = SellerProfile.objects.create(
            user=user,
            store_name=store_name,
            national_id_number=national_id_number.strip(),
            payout_method=payout_method,
            payout_account_details=payout_account_details,
            bio=bio,
            kyc_status=kyc_status,
        )
        user.is_seller = True
        user.save(update_fields=["is_seller", "updated_at"])

    return profile


def review_seller_kyc(profile: SellerProfile, approve: bool, reviewer: CustomUser) -> SellerProfile:
    """Administrative action to approve or reject seller KYC."""
    if not reviewer.is_staff:
        raise PermissionError("Only administrative staff can review KYC applications.")

    profile.kyc_status = (
        SellerProfile.KycStatus.VERIFIED if approve else SellerProfile.KycStatus.REJECTED
    )
    profile.save(update_fields=["kyc_status"])
    return profile
