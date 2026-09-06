import asyncio
import logging

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.infrastructure.broker.publisher import RabbitMQPublisher
from app.infrastructure.database.repositories import SQLAlchemyOutboxRepository
from app.infrastructure.database.session import async_session_factory

logger = logging.getLogger(__name__)


class OutboxWorker:
    """
    Outbox Worker — фоновый процесс, который:

    1. Читает pending события из outbox таблицы
    2. Публикует их в RabbitMQ (exchange 'payments', routing key из event_type)
    3. Отмечает события как processed

    Работает в цикле с задержкой (polling).
    Гарантирует доставку событий (Transactional Outbox pattern).
    """

    BATCH_SIZE = 100
    POLL_INTERVAL_SEC = 1.0  # интервал между опросами БД

    def __init__(self):
        self._publisher = RabbitMQPublisher()
        self._running = False

    async def start(self) -> None:
        """Запустить worker."""
        logger.info("Starting Outbox Worker...")

        # Подключаемся к RabbitMQ
        await self._publisher.connect()

        self._running = True

        # Основной цикл
        while self._running:
            try:
                await self._process_batch()
            except Exception as e:
                logger.exception(f"Error in outbox worker loop: {e}")
                # Ждём перед следующей попыткой
                await asyncio.sleep(5)

            # Задержка между батчами
            await asyncio.sleep(self.POLL_INTERVAL_SEC)

    async def stop(self) -> None:
        """Остановить worker."""
        logger.info("Stopping Outbox Worker...")
        self._running = False
        await self._publisher.close()

    async def _process_batch(self) -> None:
        """Обработать один батч событий из outbox."""
        async with async_session_factory() as session:
            outbox_repo = SQLAlchemyOutboxRepository(session)

            # Получаем pending события через тот же порт, что использует
            # PaymentService при записи событий — раньше тут был отдельный
            # прямой SELECT по OutboxModel, дублирующий get_pending_events
            pending_events = await outbox_repo.get_pending_events(limit=self.BATCH_SIZE)

            if not pending_events:
                return

            logger.info(f"Processing {len(pending_events)} outbox events")

            for event in pending_events:
                try:
                    await self._process_event(outbox_repo, session, event)
                except Exception as e:
                    # Если не удалось обработать — логируем и продолжаем
                    # (событие останется pending, попробуем снова в следующем батче)
                    logger.exception(
                        f"Failed to process outbox event {event['id']}: {e}"
                    )

    async def _process_event(
            self,
            outbox_repo: SQLAlchemyOutboxRepository,
            session: AsyncSession,
            event: dict,
    ) -> None:
        """
        Обработать одно событие:
        1. Опубликовать в RabbitMQ
        2. Отметить как processed
        """
        # Публикуем в RabbitMQ
        await self._publisher.publish(
            routing_key=event["event_type"],  # например, "payment.created"
            payload=event["payload"],
            message_id=str(event["id"]),
        )

        # Отмечаем как processed
        await outbox_repo.mark_processed(event["id"])
        await session.commit()

        logger.info(f"Outbox event {event['id']} processed successfully")


async def run_outbox_worker() -> None:
    """Точка входа для запуска outbox worker."""
    worker = OutboxWorker()

    try:
        await worker.start()
    except KeyboardInterrupt:
        logger.info("Keyboard interrupt received")
    finally:
        await worker.stop()


if __name__ == "__main__":
    # Запуск worker напрямую (для тестирования)
    import sys

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    asyncio.run(run_outbox_worker())