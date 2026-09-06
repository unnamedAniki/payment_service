import logging
from typing import Any

import aio_pika
from aio_pika import ExchangeType, Message

from app.core.config import settings

logger = logging.getLogger(__name__)


class RabbitMQPublisher:
    """
    Publisher для RabbitMQ.

    Отвечает за:
    - Подключение к RabbitMQ
    - Объявление exchange (payments, topic)
    - Публикацию сообщений с routing key
    """

    EXCHANGE_NAME = "payments"
    EXCHANGE_TYPE = ExchangeType.TOPIC

    def __init__(self):
        self._connection: aio_pika.abc.AbstractRobustConnection | None = None
        self._channel: aio_pika.abc.AbstractChannel | None = None
        self._exchange: aio_pika.abc.AbstractExchange | None = None

    async def connect(self) -> None:
        """Установить соединение с RabbitMQ и объявить exchange."""
        logger.info(f"Connecting to RabbitMQ at {settings.rabbit_host}...")

        self._connection = await aio_pika.connect_robust(settings.rabbit_url)
        self._channel = await self._connection.channel()

        # Объявляем exchange (topic — для гибкой маршрутизации)
        self._exchange = await self._channel.declare_exchange(
            name=self.EXCHANGE_NAME,
            type=self.EXCHANGE_TYPE,
            durable=True,  # exchange переживёт перезапуск RabbitMQ
        )

        logger.info("RabbitMQ connection established")

    async def publish(
            self,
            routing_key: str,
            payload: dict[str, Any],
            message_id: str | None = None,
    ) -> None:
        """
        Опубликовать сообщение в exchange.

        Args:
            routing_key: Ключ маршрутизации (например, "payment.created")
            payload: Тело сообщения (будет сериализовано в JSON)
            message_id: ID сообщения (для идемпотентности)
        """
        if self._exchange is None:
            raise RuntimeError("Publisher not connected. Call connect() first.")

        import json

        message = Message(
            body=json.dumps(payload).encode(),
            content_type="application/json",
            delivery_mode=aio_pika.DeliveryMode.PERSISTENT,  # сообщение сохранится на диск
            message_id=message_id,
        )

        await self._exchange.publish(
            message=message,
            routing_key=routing_key,
        )

        logger.info(
            f"Published message to '{self.EXCHANGE_NAME}' "
            f"with routing_key='{routing_key}', id={message_id}"
        )

    async def close(self) -> None:
        """Закрыть соединение."""
        if self._connection:
            await self._connection.close()
            logger.info("RabbitMQ connection closed")