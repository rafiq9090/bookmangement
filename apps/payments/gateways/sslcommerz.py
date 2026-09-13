import os
from typing import Any
import requests
from apps.orders.models import Order
from apps.payments.gateways.base import PaymentGatewayInterface


class SSLCommerzGateway(PaymentGatewayInterface):
    def __init__(self) -> None:
        self.store_id = os.environ.get("SSLCOMMERZ_STORE_ID", "testbox")
        self.store_password = os.environ.get("SSLCOMMERZ_STORE_PASSWORD", "qwerty")
        self.is_sandbox = os.environ.get("SSLCOMMERZ_IS_SANDBOX", "True").lower() in ("true", "1")
        self.base_url = (
            "https://sandbox.sslcommerz.com" if self.is_sandbox else "https://securepay.sslcommerz.com"
        )

    def initiate_payment(self, order: Order, redirect_url: str) -> dict[str, Any]:
        endpoint = f"{self.base_url}/gwprocess/v4/api.php"
        payload = {
            "store_id": self.store_id,
            "store_passwd": self.store_password,
            "total_amount": str(order.total_amount),
            "currency": "BDT",
            "tran_id": str(order.id),
            "success_url": f"{redirect_url}/success/",
            "fail_url": f"{redirect_url}/fail/",
            "cancel_url": f"{redirect_url}/cancel/",
            "ipn_url": f"{redirect_url}/ipn/",
            "cus_name": order.buyer.get_full_name() or "Valued Customer",
            "cus_email": order.buyer.email,
            "cus_phone": order.buyer.phone_number or "01700000000",
            "shipping_method": "COURIER",
            "product_name": "Used Books",
            "product_category": "Books",
            "product_profile": "physical-goods",
        }

        try:
            res = requests.post(endpoint, data=payload, timeout=10)
            data = res.json()
            if data.get("status") == "SUCCESS":
                return {"status": "SUCCESS", "gateway_url": data.get("GatewayPageURL")}
            return {"status": "FAILED", "message": data.get("failedreason", "Gateway initialization failed")}
        except requests.RequestException as exc:
            return {"status": "ERROR", "message": str(exc)}

    def verify_payment(self, payload: dict[str, Any]) -> bool:
        val_id = payload.get("val_id")
        if not val_id:
            return False

        endpoint = f"{self.base_url}/validator/api/validationserverAPI.php"
        params = {
            "val_id": val_id,
            "store_id": self.store_id,
            "store_passwd": self.store_password,
            "format": "json",
        }
        try:
            res = requests.get(endpoint, params=params, timeout=10)
            data = res.json()
            return data.get("status") in ("VALID", "VALIDATED")
        except requests.RequestException:
            return False
