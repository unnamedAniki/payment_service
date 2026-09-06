from decimal import Decimal

from app.services.entities import Currency, Payment, PaymentStatus


class TestPaymentCreate:
    """Тесты фабричного метода Payment.create()."""

    def test_create_payment_defaults(self):
        """Платёж создаётся со статусом pending."""
        payment = Payment.create(
            amount=Decimal("100.50"),
            currency=Currency.RUB,
            description="Тестовый платёж",
            webhook_url="https://example.com/webhook",
        )

        assert payment.status == PaymentStatus.PENDING
        assert payment.amount == Decimal("100.50")
        assert payment.currency == Currency.RUB
        assert payment.description == "Тестовый платёж"
        assert payment.webhook_url == "https://example.com/webhook"
        assert payment.metadata == {}
        assert payment.idempotency_key is None
        assert payment.id is not None

    def test_create_payment_with_metadata(self):
        """Платёж создаётся с метаданными."""
        metadata = {"order_id": "123", "customer": "test@example.com"}
        payment = Payment.create(
            amount=Decimal("50.00"),
            currency=Currency.USD,
            description="Order payment",
            webhook_url="https://example.com/webhook",
            metadata=metadata,
        )

        assert payment.metadata == metadata

    def test_create_payment_with_idempotency_key(self):
        """Платёж создаётся с idempotency key."""
        payment = Payment.create(
            amount=Decimal("200.00"),
            currency=Currency.EUR,
            description="Test",
            webhook_url="https://example.com/webhook",
            idempotency_key="unique-key-123",
        )

        assert payment.idempotency_key == "unique-key-123"

    def test_create_payment_generates_unique_ids(self):
        """Каждый платёж получает уникальный ID."""
        p1 = Payment.create(
            amount=Decimal("10.00"),
            currency=Currency.RUB,
            description="Test 1",
            webhook_url="https://example.com/webhook",
        )
        p2 = Payment.create(
            amount=Decimal("20.00"),
            currency=Currency.RUB,
            description="Test 2",
            webhook_url="https://example.com/webhook",
        )

        assert p1.id != p2.id


class TestPaymentStatusTransitions:
    """Тесты переходов статусов."""

    def test_mark_succeeded(self):
        """Платёж можно отметить как успешный."""
        payment = Payment.create(
            amount=Decimal("100.00"),
            currency=Currency.RUB,
            description="Test",
            webhook_url="https://example.com/webhook",
        )

        payment.mark_succeeded()

        assert payment.status == PaymentStatus.SUCCEEDED

    def test_mark_failed(self):
        """Платёж можно отметить как неуспешный."""
        payment = Payment.create(
            amount=Decimal("100.00"),
            currency=Currency.RUB,
            description="Test",
            webhook_url="https://example.com/webhook",
        )

        payment.mark_failed()

        assert payment.status == PaymentStatus.FAILED


class TestPaymentIsTerminal:
    """Тесты свойства is_terminal."""

    def test_pending_is_not_terminal(self):
        """Pending — не терминальный статус."""
        payment = Payment.create(
            amount=Decimal("100.00"),
            currency=Currency.RUB,
            description="Test",
            webhook_url="https://example.com/webhook",
        )

        assert payment.is_terminal is False

    def test_succeeded_is_terminal(self):
        """Succeeded — терминальный статус."""
        payment = Payment.create(
            amount=Decimal("100.00"),
            currency=Currency.RUB,
            description="Test",
            webhook_url="https://example.com/webhook",
        )
        payment.mark_succeeded()

        assert payment.is_terminal is True

    def test_failed_is_terminal(self):
        """Failed — терминальный статус."""
        payment = Payment.create(
            amount=Decimal("100.00"),
            currency=Currency.RUB,
            description="Test",
            webhook_url="https://example.com/webhook",
        )
        payment.mark_failed()

        assert payment.is_terminal is True