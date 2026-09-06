from decimal import Decimal

import pytest
from pydantic import ValidationError

from app.schemas.payments import PaymentCreateRequest


class TestPaymentCreateRequest:
    """Тесты валидации PaymentCreateRequest."""

    def test_valid_request(self):
        """Валидный запрос проходит валидацию."""
        data = {
            "amount": 100.50,
            "currency": "RUB",
            "description": "Тестовый платёж",
            "webhook_url": "https://example.com/webhook",
            "metadata": {"order_id": "123"},
        }

        request = PaymentCreateRequest(**data)

        assert request.amount == Decimal("100.50")
        assert request.currency == "RUB"
        assert request.description == "Тестовый платёж"
        assert str(request.webhook_url) == "https://example.com/webhook"
        assert request.metadata == {"order_id": "123"}

    def test_valid_request_all_currencies(self):
        """Все поддерживаемые валюты проходят валидацию."""
        for currency in ["RUB", "USD", "EUR"]:
            data = {
                "amount": 50.00,
                "currency": currency,
                "description": "Test",
                "webhook_url": "https://example.com/webhook",
            }

            request = PaymentCreateRequest(**data)
            assert request.currency == currency

    def test_invalid_currency(self):
        """Неподдерживаемая валюта вызывает ValidationError."""
        data = {
            "amount": 100.00,
            "currency": "GBP",
            "description": "Test",
            "webhook_url": "https://example.com/webhook",
        }

        with pytest.raises(ValidationError) as exc_info:
            PaymentCreateRequest(**data)

        assert "currency" in str(exc_info.value)

    def test_missing_required_fields(self):
        """Отсутствие обязательных полей вызывает ValidationError."""
        data = {"amount": 100.00}

        with pytest.raises(ValidationError) as exc_info:
            PaymentCreateRequest(**data)

        error_str = str(exc_info.value)
        assert "currency" in error_str
        assert "description" in error_str
        assert "webhook_url" in error_str

    def test_zero_amount(self):
        """Нулевая сумма вызывает ValidationError."""
        data = {
            "amount": 0.00,
            "currency": "RUB",
            "description": "Test",
            "webhook_url": "https://example.com/webhook",
        }

        with pytest.raises(ValidationError) as exc_info:
            PaymentCreateRequest(**data)

        assert "amount" in str(exc_info.value)

    def test_negative_amount(self):
        """Отрицательная сумма вызывает ValidationError."""
        data = {
            "amount": -10.00,
            "currency": "RUB",
            "description": "Test",
            "webhook_url": "https://example.com/webhook",
        }

        with pytest.raises(ValidationError) as exc_info:
            PaymentCreateRequest(**data)

        assert "amount" in str(exc_info.value)

    def test_too_large_amount(self):
        """Слишком большая сумма вызывает ValidationError."""
        data = {
            "amount": 9999999999.99,
            "currency": "RUB",
            "description": "Test",
            "webhook_url": "https://example.com/webhook",
        }

        with pytest.raises(ValidationError) as exc_info:
            PaymentCreateRequest(**data)

        assert "amount" in str(exc_info.value)

    def test_empty_description(self):
        """Пустое описание вызывает ValidationError."""
        data = {
            "amount": 100.00,
            "currency": "RUB",
            "description": "",
            "webhook_url": "https://example.com/webhook",
        }

        with pytest.raises(ValidationError) as exc_info:
            PaymentCreateRequest(**data)

        assert "description" in str(exc_info.value)

    def test_invalid_webhook_url(self):
        """Невалидный webhook URL вызывает ValidationError."""
        data = {
            "amount": 100.00,
            "currency": "RUB",
            "description": "Test",
            "webhook_url": "not-a-url",
        }

        with pytest.raises(ValidationError) as exc_info:
            PaymentCreateRequest(**data)

        assert "webhook_url" in str(exc_info.value)

    def test_metadata_defaults_to_empty_dict(self):
        """Metadata по умолчанию — пустой dict."""
        data = {
            "amount": 100.00,
            "currency": "RUB",
            "description": "Test",
            "webhook_url": "https://example.com/webhook",
        }

        request = PaymentCreateRequest(**data)
        assert request.metadata == {}

    def test_metadata_with_complex_data(self):
        """Metadata может содержать сложные структуры."""
        data = {
            "amount": 100.00,
            "currency": "RUB",
            "description": "Test",
            "webhook_url": "https://example.com/webhook",
            "metadata": {
                "order_id": "123",
                "items": [{"id": 1, "name": "Product"}],
                "nested": {"key": "value"},
            },
        }

        request = PaymentCreateRequest(**data)
        assert request.metadata["order_id"] == "123"
        assert len(request.metadata["items"]) == 1
        assert request.metadata["nested"]["key"] == "value"

    def test_description_strips_whitespace(self):
        """Пробелы в начале и конце описания удаляются."""
        data = {
            "amount": 100.00,
            "currency": "RUB",
            "description": "  Test description  ",
            "webhook_url": "https://example.com/webhook",
        }

        request = PaymentCreateRequest(**data)
        assert request.description == "Test description"