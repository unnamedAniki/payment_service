from datetime import datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, field_validator

from app.services.entities import Currency, PaymentStatus


class PaymentCreateRequest(BaseModel):
    """
    Схема для создания платежа (POST /api/v1/payments).

    Валидирует входные данные от клиента.
    """
    model_config = ConfigDict(
        str_strip_whitespace=True,
        use_enum_values=True,
    )

    amount: Decimal = Field(
        ...,
        gt=0,
        decimal_places=2,
        description="Сумма платежа (должна быть > 0)",
        examples=[100.50],
    )
    currency: Currency = Field(
        ...,
        description="Валюта платежа (RUB, USD, EUR)",
        examples=["RUB"],
    )
    description: str = Field(
        ...,
        min_length=1,
        max_length=500,
        description="Описание платежа",
        examples=["Оплата заказа #12345"],
    )
    webhook_url: HttpUrl = Field(
        ...,
        description="URL для webhook уведомления о результате",
        examples=["https://example.com/webhook"],
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Дополнительные метаданные (JSON)",
        examples=[{"order_id": "12345", "customer_email": "test@example.com"}],
    )

    @field_validator("amount")
    @classmethod
    def validate_amount(cls, v: Decimal) -> Decimal:
        """Проверяем, что сумма не слишком большая."""
        if v > Decimal("999999999.99"):
            raise ValueError("Сумма платежа не может превышать 999999999.99")
        return v


class PaymentCreateResponse(BaseModel):
    """
    Схема ответа при создании платежа (202 Accepted).

    Возвращается клиенту после POST /api/v1/payments.
    """
    model_config = ConfigDict(
        from_attributes=True,
    )

    payment_id: UUID = Field(
        ...,
        description="Уникальный идентификатор платежа",
    )
    status: PaymentStatus = Field(
        ...,
        description="Текущий статус платежа",
    )
    created_at: datetime = Field(
        ...,
        description="Время создания платежа",
    )


class PaymentResponse(BaseModel):
    """
    Схема для получения детальной информации о платеже (GET /api/v1/payments/{id}).

    Возвращает полную информацию о платеже.
    """
    model_config = ConfigDict(
        from_attributes=True,
        use_enum_values=True,
    )

    id: UUID = Field(
        ...,
        description="Уникальный идентификатор платежа",
    )
    amount: Decimal = Field(
        ...,
        description="Сумма платежа",
    )
    currency: Currency = Field(
        ...,
        description="Валюта платежа",
    )
    description: str = Field(
        ...,
        description="Описание платежа",
    )
    webhook_url: str = Field(
        ...,
        description="URL для webhook уведомления",
    )
    status: PaymentStatus = Field(
        ...,
        description="Текущий статус платежа",
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Дополнительные метаданные",
    )
    idempotency_key: str | None = Field(
        default=None,
        description="Idempotency key (если был передан)",
    )
    created_at: datetime = Field(
        ...,
        description="Время создания платежа",
    )


class ErrorResponse(BaseModel):
    """
    Схема для ошибок API.

    Используется для возврата структурированных ошибок.
    """
    error: str = Field(
        ...,
        description="Тип ошибки",
        examples=["PaymentNotFound", "DuplicateIdempotencyKey"],
    )
    message: str = Field(
        ...,
        description="Описание ошибки",
        examples=["Payment with id '...' not found"],
    )
    details: dict[str, Any] | None = Field(
        default=None,
        description="Дополнительная информация об ошибке",
    )