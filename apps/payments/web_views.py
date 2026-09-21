from decimal import Decimal
import uuid
from django.db import transaction
from django.db.models import Sum
from django.shortcuts import redirect, render

from apps.listings.web_views import get_or_create_seller_user
from apps.orders.services.cart import get_cart_items_for_request
from apps.payments.models import EscrowHold, PayoutBatch, SellerLedger


def seller_wallet_view(request):
    """
    Page 8: Seller Wallet & Payouts (/seller/wallet/)
    Displays available balance, escrow pending hold, payout withdrawal form,
    and double-entry financial ledger records.
    """
    seller = get_or_create_seller_user(request)
    _, _, cart_count = get_cart_items_for_request(request)

    # Handle Payout Withdrawal POST
    if request.method == "POST":
        amount_str = request.POST.get("amount", "0").strip()
        payout_method = request.POST.get("payout_method", "bkash")
        account_details = request.POST.get("account_details", "").strip()

        try:
            amount = Decimal(amount_str)
        except Exception:
            amount = Decimal("0.00")

        if amount > 0 and account_details:
            with transaction.atomic():
                PayoutBatch.objects.create(
                    seller=seller,
                    amount=amount,
                    payout_method=payout_method,
                    account_details=account_details,
                    status=PayoutBatch.Status.REQUESTED,
                )
                SellerLedger.objects.create(
                    seller=seller,
                    entry_type=SellerLedger.EntryType.PAYOUT_DEBIT,
                    amount=amount,
                    reference_id=f"WDL-{uuid.uuid4().hex[:6].upper()}",
                )
            return redirect("seller_wallet")

    # Financial balance calculation
    credits = SellerLedger.objects.filter(
        seller=seller,
        entry_type=SellerLedger.EntryType.SALE_CREDIT,
    ).aggregate(total=Sum("amount"))["total"] or Decimal("0.00")

    debits = SellerLedger.objects.filter(
        seller=seller,
        entry_type__in=[
            SellerLedger.EntryType.PLATFORM_FEE,
            SellerLedger.EntryType.PAYOUT_DEBIT,
            SellerLedger.EntryType.REFUND_DEBIT,
        ],
    ).aggregate(total=Sum("amount"))["total"] or Decimal("0.00")

    available_balance = max(Decimal("0.00"), credits - debits)

    escrow_agg = EscrowHold.objects.filter(
        shipment__seller=seller,
        status=EscrowHold.EscrowStatus.HELD,
    ).aggregate(total=Sum("seller_net_amount"))
    escrow_balance = escrow_agg["total"] or Decimal("0.00")

    ledger_entries = SellerLedger.objects.filter(seller=seller).order_by("-created_at")[:20]
    payout_requests = PayoutBatch.objects.filter(seller=seller).order_by("-created_at")[:10]

    return render(
        request,
        "payments/wallet.html",
        {
            "available_balance": available_balance,
            "escrow_balance": escrow_balance,
            "total_earnings": credits,
            "ledger_entries": ledger_entries,
            "payout_requests": payout_requests,
            "cart_count": cart_count,
        },
    )
