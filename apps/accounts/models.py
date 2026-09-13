from decimal import Decimal
from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.db import models


class CustomUserManager(BaseUserManager):
    def create_user(self, email: str, password: str | None = None, **extra_fields) -> "CustomUser":
        if not email:
            raise ValueError("An email address is required for registration.")
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email: str, password: str | None = None, **extra_fields) -> "CustomUser":
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        extra_fields.setdefault("is_active", True)

        if extra_fields.get("is_staff") is not True:
            raise ValueError("Superuser must have is_staff=True.")
        if extra_fields.get("is_superuser") is not True:
            raise ValueError("Superuser must have is_superuser=True.")

        return self.create_user(email, password, **extra_fields)


class CustomUser(AbstractUser):
    username = None  # Replaced by email as primary identifier
    email = models.EmailField(unique=True, db_index=True)
    phone_number = models.CharField(max_length=20, blank=True)
    is_seller = models.BooleanField(default=False)
    avatar = models.ImageField(upload_to="avatars/", blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = CustomUserManager()

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = []

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "User"
        verbose_name_plural = "Users"

    def __str__(self) -> str:
        return self.email


class SellerProfile(models.Model):
    class KycStatus(models.TextChoices):
        UNVERIFIED = "UNVERIFIED", "Unverified"
        PENDING = "PENDING", "Pending Review"
        VERIFIED = "VERIFIED", "Verified"
        REJECTED = "REJECTED", "Rejected"

    class PayoutMethod(models.TextChoices):
        BKASH = "BKASH", "bKash"
        NAGAD = "NAGAD", "Nagad"
        BANK = "BANK", "Bank Transfer"

    user = models.OneToOneField(CustomUser, on_delete=models.CASCADE, related_name="seller_profile")
    store_name = models.CharField(max_length=120, unique=True)
    bio = models.TextField(blank=True)
    kyc_status = models.CharField(
        max_length=15,
        choices=KycStatus.choices,
        default=KycStatus.UNVERIFIED,
        db_index=True,
    )
    national_id_number = models.CharField(max_length=50, blank=True)
    payout_method = models.CharField(
        max_length=10,
        choices=PayoutMethod.choices,
        default=PayoutMethod.BKASH,
    )
    payout_account_details = models.CharField(max_length=120, blank=True)
    rating_avg = models.DecimalField(max_digits=3, decimal_places=2, default=Decimal("5.00"))
    rating_count = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Seller Profile"
        verbose_name_plural = "Seller Profiles"

    def __str__(self) -> str:
        return f"{self.store_name} ({self.user.email})"


class Address(models.Model):
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name="addresses")
    recipient_name = models.CharField(max_length=100)
    phone_number = models.CharField(max_length=20)
    street_address = models.CharField(max_length=255)
    city = models.CharField(max_length=100)
    state_division = models.CharField(max_length=100)
    postal_code = models.CharField(max_length=20)
    country = models.CharField(max_length=50, default="Bangladesh")
    is_default = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-is_default", "-created_at"]
        verbose_name = "Address"
        verbose_name_plural = "Addresses"

    def __str__(self) -> str:
        return f"{self.recipient_name} - {self.city}, {self.country}"

    def save(self, *args, **kwargs) -> None:
        if self.is_default:
            Address.objects.filter(user=self.user, is_default=True).exclude(pk=self.pk).update(is_default=False)
        super().save(*args, **kwargs)
