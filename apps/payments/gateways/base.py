from abc import ABC, abstractmethod
from typing import Any
from apps.orders.models import Order


class PaymentGatewayInterface(ABC):
    @abstractmethod
    def initiate_payment(self, order: Order, redirect_url: str) -> dict[str, Any]:
        """Initiates session with gateway and yields payment gateway URL."""
        pass

    @abstractmethod
    def verify_payment(self, payload: dict[str, Any]) -> bool:
        """Validates webhook or IPN authenticity and payment status."""
        pass
