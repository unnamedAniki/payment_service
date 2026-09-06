import asyncio
import json
import logging
import random
from datetime import datetime, timezone
from decimal import Decimal
from uuid import UUID

import httpx
from faststream import ContextRepo, FastStream
from faststream.rabbit import RabbitBroker, RabbitExchange, RabbitQueue, RabbitRouter
from faststream.rabbit.schemas.constants import ExchangeType
from faststream.rabbit.annotations import Logger

from app.core.config import settings
from app.services.exceptions import PaymentNotFoundError
from app.services.services import PaymentService
from app.infrastructure.database.repositories import (
    SQLAlchemyOutboxRepository,
    SQLAlchemyPaymentRepository,
)
from app.infrastructure.database.session import async_session_factory

logger = logging.getLogger(__name__)

# Создаём FastStream приложение
broker = RabbitBroker(settings.rabbit_url)

# Объявляем exchange (должен совпадать с publisher)
payments_exchange = RabbitExchange(
    name="payments",
    type=ExchangeType.TOPIC,
    durable=True,
)

# Объявляем основную очередь
payments_queue = RabbitQueue(
    name="payments.new",
    durable=True,
)

# Объявляем DLQ — отдельная очередь для упавших сообщений
dlq_queue = RabbitQueue(
    name="payments.new.dlq",
    durable=True,
)

# Создаём роутер для consumer
router = RabbitRouter()


async def emulate_payment_processing() -> bool:
    """
    Эмуляция обработки платежа через внешний шлюз.

    - Задержка 2-5 секунд
    - 90% успех, 10% ошибка

    Returns:
        True если успех, False если ошибка
    """
    # Имитируем задержку обработки (2-5 сек)
    processing_time = random.uniform(
        settings.payment_processing_min_sec,
        settings.payment_processing_max_sec,
    )
    await asyncio.sleep(processing_time)

    # Имитируем результат (90% успех, 10% ошибка)
    success = random.random() < settings.payment_success_rate

    return success


async def send_webhook(webhook_url: str, payment_data: dict) -> bool:
    """
    Отправка webhook уведомления клиенту.

    Args:
        webhook_url: URL для уведомления
        payment_data: Данные о платеже

    Returns:
        True если успешно, False если ошибка
    """
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(
                webhook_url,
                json=payment_data,
                headers={"Content-Type": "application/json"},
            )

            if response.status_code >= 400:
                logger.warning(
                    f"Webhook returned status {response.status_code} for {webhook_url}"
                )
                return False

            logger.info(f"Webhook sent successfully to {webhook_url}")
            return True

    except Exception as e:
        logger.exception(f"Failed to send webhook to {webhook_url}: {e}")
        return False


@router.subscriber(
    queue=payments_queue,
    exchange=payments_exchange,
    retry=3,  # 3 попытки с экспоненциальной задержкой
)
async def process_payment(
        body: dict,
        logger: Logger,
):
    """
    Обработка платежа из очереди payments.new.

    Алгоритм:
    1. Извлекаем данные из сообщения
    2. Эмулируем обработку платежа (2-5 сек, 90% успех)
    3. Обновляем статус в БД
    4. Отправляем webhook уведомление
    5. При ошибке — retry (3 попытки), потом в DLQ
    """
    logger.info(f"Processing payment message: {body}")

    payment_id = UUID(body["payment_id"])
    webhook_url = body["webhook_url"]

    # 1. Эмулируем обработку платежа
    success = await emulate_payment_processing()

    logger.info(
        f"Payment {payment_id} processing {'succeeded' if success else 'failed'}"
    )

    # 2. Применяем результат через доменный сервис (Payment.mark_succeeded/
    # mark_failed), а не правкой поля в ORM-модели напрямую
    async with async_session_factory() as session:
        payment_service = PaymentService(
            SQLAlchemyPaymentRepository(session),
            SQLAlchemyOutboxRepository(session),
        )
        try:
            payment = await payment_service.apply_payment_result(payment_id, success)
        except PaymentNotFoundError:
            logger.error(f"Payment {payment_id} not found in database")
            raise ValueError(f"Payment {payment_id} not found")

        await session.commit()

    # 3. Отправляем webhook уведомление
    webhook_data = {
        "payment_id": str(payment_id),
        "status": payment.status.value,
        "amount": body["amount"],
        "currency": body["currency"],
        "metadata": body.get("metadata", {}),
    }

    webhook_success = await send_webhook(webhook_url, webhook_data)

    if not webhook_success:
        logger.warning(
            f"Failed to send webhook for payment {payment_id}, "
            f"but payment status updated to {payment.status.value}"
        )
        # Не кидаем исключение — платёж уже обработан, webhook можно попробовать позже
        # (в реальном проекте тут может быть отдельный retry механизм для webhook)

    logger.info(f"Payment {payment_id} fully processed with status {payment.status.value}")


@router.subscriber(
    queue=dlq_queue,
    exchange=payments_exchange,
)
async def handle_dead_letter(body: dict, logger: Logger):
    """
    Обработчик Dead Letter Queue.

    Сюда попадают сообщения, которые не удалось обработать после 3 попыток.
    Можно логировать, отправлять алерты, сохранять для ручной обработки.
    """
    logger.error(
        f"Message ended up in DLQ after 3 retries: {body}. "
        f"Manual intervention required."
    )

# Подключаем роутер к broker
broker.include_router(router)


async def run_consumer() -> None:
    """Точка входа для запуска consumer."""
    logger.info("Starting FastStream consumer...")

    # Создаём FastStream app
    app = FastStream(broker)

    # Запускаем
    await app.run()


if __name__ == "__main__":
    # Запуск consumer напрямую (для тестирования)
    import sys

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    asyncio.run(run_consumer())