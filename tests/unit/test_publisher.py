from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.infrastructure.broker.publisher import RabbitMQPublisher


class TestRabbitMQPublisher:
    """Тесты RabbitMQ publisher."""

    @patch("app.infrastructure.broker.publisher.aio_pika.connect_robust")
    async def test_connect_success(self, mock_connect):
        """Успешное подключение к RabbitMQ."""
        from aio_pika import ExchangeType

        mock_connection = AsyncMock()
        mock_channel = AsyncMock()
        mock_exchange = AsyncMock()

        mock_connect.return_value = mock_connection
        mock_connection.channel.return_value = mock_channel
        mock_channel.declare_exchange.return_value = mock_exchange

        publisher = RabbitMQPublisher()
        await publisher.connect()

        mock_connect.assert_called_once()
        mock_connection.channel.assert_called_once()
        mock_channel.declare_exchange.assert_called_once_with(
            name="payments",
            type=ExchangeType.TOPIC,
            durable=True,
        )

    async def test_publish_without_connection(self):
        """Публикация без подключения вызывает RuntimeError."""
        publisher = RabbitMQPublisher()

        with pytest.raises(RuntimeError, match="not connected"):
            await publisher.publish(
                routing_key="payment.created",
                payload={"test": "data"},
            )

    @patch("app.infrastructure.broker.publisher.aio_pika.connect_robust")
    async def test_publish_success(self, mock_connect):
        """Успешная публикация сообщения."""
        mock_connection = AsyncMock()
        mock_channel = AsyncMock()
        mock_exchange = AsyncMock()

        mock_connect.return_value = mock_connection
        mock_connection.channel.return_value = mock_channel
        mock_channel.declare_exchange.return_value = mock_exchange

        publisher = RabbitMQPublisher()
        await publisher.connect()

        await publisher.publish(
            routing_key="payment.created",
            payload={"payment_id": "123", "amount": "100.50"},
            message_id="msg-123",
        )

        mock_exchange.publish.assert_called_once()

    @patch("app.infrastructure.broker.publisher.aio_pika.connect_robust")
    async def test_close_connection(self, mock_connect):
        """Закрытие соединения."""
        mock_connection = AsyncMock()
        mock_channel = AsyncMock()
        mock_exchange = AsyncMock()

        mock_connect.return_value = mock_connection
        mock_connection.channel.return_value = mock_channel
        mock_channel.declare_exchange.return_value = mock_exchange

        publisher = RabbitMQPublisher()
        await publisher.connect()
        await publisher.close()

        mock_connection.close.assert_called_once()