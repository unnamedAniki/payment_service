from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from app.services.entities import Currency, PaymentStatus
from app.services.exceptions import PaymentNotFoundError
from app.infrastructure.broker.consumer import (
    emulate_payment_processing,
    process_payment,
    send_webhook,
)


class TestEmulatePaymentProcessing:
    """Тесты эмуляции обработки платежа."""

    @patch("app.infrastructure.broker.consumer.asyncio.sleep")
    @patch("app.infrastructure.broker.consumer.random.uniform")
    @patch("app.infrastructure.broker.consumer.random.random")
    async def test_emulate_success(self, mock_random, mock_uniform, mock_sleep):
        """Эмуляция успешной обработки."""
        mock_uniform.return_value = 2.5
        mock_random.return_value = 0.5  # < 0.9 = success
        mock_sleep.return_value = None

        result = await emulate_payment_processing()

        assert result is True
        mock_sleep.assert_called_once_with(2.5)

    @patch("app.infrastructure.broker.consumer.asyncio.sleep")
    @patch("app.infrastructure.broker.consumer.random.uniform")
    @patch("app.infrastructure.broker.consumer.random.random")
    async def test_emulate_failure(self, mock_random, mock_uniform, mock_sleep):
        """Эмуляция неуспешной обработки."""
        mock_uniform.return_value = 3.0
        mock_random.return_value = 0.95  # >= 0.9 = failure
        mock_sleep.return_value = None

        result = await emulate_payment_processing()

        assert result is False


class TestSendWebhook:
    """Тесты отправки webhook."""

    @patch("app.infrastructure.broker.consumer.httpx.AsyncClient")
    async def test_send_webhook_success(self, mock_client_class):
        """Успешная отправка webhook."""
        mock_client = AsyncMock()
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_client.post.return_value = mock_response
        mock_client.__aenter__.return_value = mock_client
        mock_client_class.return_value = mock_client

        result = await send_webhook(
            "https://example.com/webhook",
            {"payment_id": "123", "status": "succeeded"},
        )

        assert result is True
        mock_client.post.assert_called_once()

    @patch("app.infrastructure.broker.consumer.httpx.AsyncClient")
    async def test_send_webhook_http_error(self, mock_client_class):
        """Webhook вернул HTTP ошибку."""
        mock_client = AsyncMock()
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_client.post.return_value = mock_response
        mock_client.__aenter__.return_value = mock_client
        mock_client_class.return_value = mock_client

        result = await send_webhook(
            "https://example.com/webhook",
            {"payment_id": "123", "status": "succeeded"},
        )

        assert result is False

    @patch("app.infrastructure.broker.consumer.httpx.AsyncClient")
    async def test_send_webhook_connection_error(self, mock_client_class):
        """Ошибка соединения при отправке webhook."""
        mock_client = AsyncMock()
        mock_client.post.side_effect = Exception("Connection error")
        mock_client.__aenter__.return_value = mock_client
        mock_client_class.return_value = mock_client

        result = await send_webhook(
            "https://example.com/webhook",
            {"payment_id": "123", "status": "succeeded"},
        )

        assert result is False


class TestProcessPayment:
    """Тесты обработки платежа из очереди."""

    @patch("app.infrastructure.broker.consumer.send_webhook")
    @patch("app.infrastructure.broker.consumer.emulate_payment_processing")
    @patch("app.infrastructure.broker.consumer.PaymentService")
    @patch("app.infrastructure.broker.consumer.async_session_factory")
    async def test_process_payment_success(
        self, mock_session_factory, mock_payment_service_class, mock_emulate, mock_webhook
    ):
        """Успешная обработка платежа."""
        payment_id = uuid4()
        body = {
            "payment_id": str(payment_id),
            "amount": "100.50",
            "currency": "RUB",
            "webhook_url": "https://example.com/webhook",
            "metadata": {"order_id": "123"},
        }

        mock_emulate.return_value = True
        mock_webhook.return_value = True

        mock_session = AsyncMock()
        mock_session_factory.return_value.__aenter__.return_value = mock_session

        mock_payment = MagicMock()
        mock_payment.id = payment_id
        mock_payment.status = PaymentStatus.SUCCEEDED
        mock_payment_service = AsyncMock()
        mock_payment_service.apply_payment_result.return_value = mock_payment
        mock_payment_service_class.return_value = mock_payment_service

        mock_logger = MagicMock()

        await process_payment(body, mock_logger)

        mock_emulate.assert_called_once()
        mock_payment_service.apply_payment_result.assert_called_once_with(
            payment_id, True
        )
        mock_session.commit.assert_called_once()
        mock_webhook.assert_called_once()

    @patch("app.infrastructure.broker.consumer.send_webhook")
    @patch("app.infrastructure.broker.consumer.emulate_payment_processing")
    @patch("app.infrastructure.broker.consumer.PaymentService")
    @patch("app.infrastructure.broker.consumer.async_session_factory")
    async def test_process_payment_failure(
        self, mock_session_factory, mock_payment_service_class, mock_emulate, mock_webhook
    ):
        """Неуспешная обработка платежа."""
        payment_id = uuid4()
        body = {
            "payment_id": str(payment_id),
            "amount": "100.50",
            "currency": "RUB",
            "webhook_url": "https://example.com/webhook",
            "metadata": {},
        }

        mock_emulate.return_value = False
        mock_webhook.return_value = True

        mock_session = AsyncMock()
        mock_session_factory.return_value.__aenter__.return_value = mock_session

        mock_payment = MagicMock()
        mock_payment.id = payment_id
        mock_payment.status = PaymentStatus.FAILED
        mock_payment_service = AsyncMock()
        mock_payment_service.apply_payment_result.return_value = mock_payment
        mock_payment_service_class.return_value = mock_payment_service

        mock_logger = MagicMock()

        await process_payment(body, mock_logger)

        mock_payment_service.apply_payment_result.assert_called_once_with(
            payment_id, False
        )

    @patch("app.infrastructure.broker.consumer.emulate_payment_processing")
    @patch("app.infrastructure.broker.consumer.PaymentService")
    @patch("app.infrastructure.broker.consumer.async_session_factory")
    async def test_process_payment_not_found(
        self, mock_session_factory, mock_payment_service_class, mock_emulate
    ):
        """Платёж не найден в БД."""
        payment_id = uuid4()
        body = {
            "payment_id": str(payment_id),
            "amount": "100.50",
            "currency": "RUB",
            "webhook_url": "https://example.com/webhook",
            "metadata": {},
        }

        mock_emulate.return_value = True

        mock_session = AsyncMock()
        mock_session_factory.return_value.__aenter__.return_value = mock_session

        mock_payment_service = AsyncMock()
        mock_payment_service.apply_payment_result.side_effect = PaymentNotFoundError(
            str(payment_id)
        )
        mock_payment_service_class.return_value = mock_payment_service

        mock_logger = MagicMock()

        with pytest.raises(ValueError, match="not found"):
            await process_payment(body, mock_logger)