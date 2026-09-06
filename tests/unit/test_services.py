from decimal import Decimal
from uuid import uuid4

import pytest

from app.services.entities import Currency, Payment, PaymentStatus
from app.services.exceptions import PaymentNotFoundError


class TestCreatePayment:
    """Тесты PaymentService.create_payment()."""

    async def test_create_payment_success(
        self, payment_service, mock_payment_repo, mock_outbox_repo
    ):
        """Успешное создание платежа."""
        mock_payment_repo.get_by_idempotency_key.return_value = None

        result = await payment_service.create_payment(
            amount=Decimal("100.50"),
            currency=Currency.RUB,
            description="Тестовый платёж",
            webhook_url="https://example.com/webhook",
            metadata={"order_id": "123"},
        )

        assert result.status == PaymentStatus.PENDING
        assert result.amount == Decimal("100.50")
        assert result.currency == Currency.RUB
        assert result.description == "Тестовый платёж"
        assert result.metadata == {"order_id": "123"}

        mock_payment_repo.save.assert_called_once_with(result)
        mock_outbox_repo.save_event.assert_called_once()

        outbox_call = mock_outbox_repo.save_event.call_args
        assert outbox_call.kwargs["event_type"] == "payment.created"
        assert outbox_call.kwargs["payload"]["payment_id"] == str(result.id)

    async def test_create_payment_with_new_idempotency_key(
        self, payment_service, mock_payment_repo, mock_outbox_repo
    ):
        """Создание платежа с новым idempotency key."""
        mock_payment_repo.get_by_idempotency_key.return_value = None

        result = await payment_service.create_payment(
            amount=Decimal("50.00"),
            currency=Currency.USD,
            description="Test",
            webhook_url="https://example.com/webhook",
            idempotency_key="unique-key-123",
        )

        assert result.idempotency_key == "unique-key-123"
        mock_payment_repo.get_by_idempotency_key.assert_called_once_with(
            "unique-key-123"
        )
        mock_payment_repo.save.assert_called_once()

    async def test_create_payment_duplicate_idempotency_key(
        self, payment_service, mock_payment_repo, mock_outbox_repo
    ):
        """Повторный запрос с тем же idempotency key возвращает существующий платёж."""
        existing_payment = Payment.create(
            amount=Decimal("100.00"),
            currency=Currency.RUB,
            description="Original",
            webhook_url="https://example.com/webhook",
            idempotency_key="dup-key",
        )
        mock_payment_repo.get_by_idempotency_key.return_value = existing_payment

        result = await payment_service.create_payment(
            amount=Decimal("999.00"),
            currency=Currency.USD,
            description="Duplicate attempt",
            webhook_url="https://other.com/webhook",
            idempotency_key="dup-key",
        )

        assert result.id == existing_payment.id
        assert result.amount == Decimal("100.00")
        mock_payment_repo.save.assert_not_called()
        mock_outbox_repo.save_event.assert_not_called()

    async def test_create_payment_without_idempotency_key(
        self, payment_service, mock_payment_repo, mock_outbox_repo
    ):
        """Создание платежа без idempotency key не проверяет дубликаты."""
        result = await payment_service.create_payment(
            amount=Decimal("75.00"),
            currency=Currency.EUR,
            description="No key",
            webhook_url="https://example.com/webhook",
        )

        assert result.idempotency_key is None
        mock_payment_repo.get_by_idempotency_key.assert_not_called()
        mock_payment_repo.save.assert_called_once()


class TestGetPayment:
    """Тесты PaymentService.get_payment()."""

    async def test_get_payment_success(self, payment_service, mock_payment_repo):
        """Успешное получение платежа."""
        payment_id = uuid4()
        expected_payment = Payment.create(
            amount=Decimal("100.00"),
            currency=Currency.RUB,
            description="Test",
            webhook_url="https://example.com/webhook",
        )
        expected_payment.id = payment_id
        mock_payment_repo.get_by_id.return_value = expected_payment

        result = await payment_service.get_payment(payment_id)

        assert result.id == payment_id
        assert result.amount == Decimal("100.00")
        mock_payment_repo.get_by_id.assert_called_once_with(payment_id)

    async def test_get_payment_not_found(self, payment_service, mock_payment_repo):
        """Получение несуществующего платежа кидает PaymentNotFoundError."""
        payment_id = uuid4()
        mock_payment_repo.get_by_id.return_value = None

        with pytest.raises(PaymentNotFoundError) as exc_info:
            await payment_service.get_payment(payment_id)

        assert str(payment_id) in str(exc_info.value)
        mock_payment_repo.get_by_id.assert_called_once_with(payment_id)


class TestApplyPaymentResult:
    """Тесты PaymentService.apply_payment_result()."""

    async def test_apply_payment_result_success(
        self, payment_service, mock_payment_repo
    ):
        """Успешный результат переводит платёж в SUCCEEDED через домен."""
        payment_id = uuid4()
        payment = Payment.create(
            amount=Decimal("100.00"),
            currency=Currency.RUB,
            description="Test",
            webhook_url="https://example.com/webhook",
        )
        payment.id = payment_id
        mock_payment_repo.get_by_id.return_value = payment

        result = await payment_service.apply_payment_result(payment_id, success=True)

        assert result.status == PaymentStatus.SUCCEEDED
        mock_payment_repo.save.assert_called_once_with(payment)

    async def test_apply_payment_result_failure(
        self, payment_service, mock_payment_repo
    ):
        """Неуспешный результат переводит платёж в FAILED через домен."""
        payment_id = uuid4()
        payment = Payment.create(
            amount=Decimal("100.00"),
            currency=Currency.RUB,
            description="Test",
            webhook_url="https://example.com/webhook",
        )
        payment.id = payment_id
        mock_payment_repo.get_by_id.return_value = payment

        result = await payment_service.apply_payment_result(payment_id, success=False)

        assert result.status == PaymentStatus.FAILED
        mock_payment_repo.save.assert_called_once_with(payment)

    async def test_apply_payment_result_not_found(
        self, payment_service, mock_payment_repo
    ):
        """Несуществующий платёж кидает PaymentNotFoundError."""
        payment_id = uuid4()
        mock_payment_repo.get_by_id.return_value = None

        with pytest.raises(PaymentNotFoundError):
            await payment_service.apply_payment_result(payment_id, success=True)

        mock_payment_repo.save.assert_not_called()