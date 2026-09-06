from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal
from enum import Enum
from typing import Any
from uuid import UUID, uuid4


class Currency(str, Enum):
    """Валюты, поддерживаемые сервисом."""
    RUB = "RUB"
    USD = "USD"
    EUR = "EUR"


class PaymentStatus(str, Enum):
    """Статусы платежа."""
    PENDING = "pending"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


@dataclass
class Payment:
    """
    Доменная сущность платежа.

    Не зависит от SQLAlchemy, Pydantic и других фреймворков —
    это чистая бизнес-логика.
    """
    id: UUID
    amount: Decimal
    currency: Currency
    description: str
    webhook_url: str
    status: PaymentStatus = PaymentStatus.PENDING
    metadata: dict[str, Any] = field(default_factory=dict)
    idempotency_key: str | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    @staticmethod
    def create(
            amount: Decimal,
            currency: Currency,
            description: str,
            webhook_url: str,
            metadata: dict[str, Any] | None = None,
            idempotency_key: str | None = None,
    ) -> "Payment":
        """Фабричный метод для создания нового платежа."""
        return Payment(
            id=uuid4(),
            amount=amount,
            currency=currency,
            description=description,
            webhook_url=webhook_url,
            metadata=metadata or {},
            idempotency_key=idempotency_key,
            status=PaymentStatus.PENDING,
        )

    def mark_succeeded(self) -> None:
        """Отметить платёж как успешный."""
        self.status = PaymentStatus.SUCCEEDED

    def mark_failed(self) -> None:
        """Отметить платёж как неуспешный."""
        self.status = PaymentStatus.FAILED

    @property
    def is_terminal(self) -> bool:
        """Платёж в терминальном состоянии (нельзя изменить)."""
        return self.status in (PaymentStatus.SUCCEEDED, PaymentStatus.FAILED)