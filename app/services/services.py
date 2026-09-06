import logging
from uuid import UUID

from app.services.entities import Payment, PaymentStatus
from app.services.exceptions import (
    DuplicateIdempotencyKeyError,
    PaymentNotFoundError,
)
from app.services.repositories import OutboxRepository, PaymentRepository

logger = logging.getLogger(__name__)


class PaymentService:
    """
    Сервисный слой для работы с платежами.

    Содержит бизнес-логику:
    - Создание платежа с проверкой idempotency
    - Запись события в outbox (в той же транзакции!)
    - Получение платежа по ID

    НЕ знает про HTTP, SQLAlchemy, RabbitMQ — только про порты (ABC).
    """

    def __init__(
            self,
            payment_repo: PaymentRepository,
            outbox_repo: OutboxRepository,
    ):
        self._payment_repo = payment_repo
        self._outbox_repo = outbox_repo

    async def create_payment(
            self,
            amount,
            currency,
            description: str,
            webhook_url: str,
            metadata: dict | None = None,
            idempotency_key: str | None = None,
    ) -> Payment:
        """
        Создание платежа.

        Алгоритм:
        1. Если передан idempotency_key — проверяем, нет ли уже такого платежа
        2. Если есть — возвращаем существующий (защита от дублей)
        3. Создаём новый платёж со статусом pending
        4. Сохраняем в БД
        5. Пишем событие в outbox (в той же транзакции!)
        6. Возвращаем платёж

        ВАЖНО: коммит транзакции делает вызывающий код (API endpoint).
        Это гарантирует атомарность: либо платёж + outbox, либо ничего.
        """
        # 1. Проверяем idempotency key
        if idempotency_key:
            existing_payment = await self._payment_repo.get_by_idempotency_key(
                idempotency_key
            )
            if existing_payment:
                logger.info(
                    f"Duplicate idempotency key '{idempotency_key}' — "
                    f"returning existing payment {existing_payment.id}"
                )
                # Возвращаем существующий платёж (не создаём новый!)
                return existing_payment

        # 2. Создаём новый платёж через фабричный метод
        payment = Payment.create(
            amount=amount,
            currency=currency,
            description=description,
            webhook_url=webhook_url,
            metadata=metadata,
            idempotency_key=idempotency_key,
        )

        # 3. Сохраняем платёж в БД (flush, не commit!)
        await self._payment_repo.save(payment)

        # 4. Пишем событие в outbox (в той же транзакции!)
        # Это Transactional Outbox pattern — гарантия доставки
        await self._outbox_repo.save_event(
            event_type="payment.created",
            payload={
                "payment_id": str(payment.id),
                "amount": str(payment.amount),
                "currency": payment.currency.value,
                "webhook_url": payment.webhook_url,
                "metadata": payment.metadata,
            },
        )

        logger.info(
            f"Payment {payment.id} created with status {payment.status.value}"
        )

        return payment

    async def get_payment(self, payment_id: UUID) -> Payment:
        """
        Получение платежа по ID.

        Если платёж не найден — кидаем PaymentNotFoundError.
        """
        payment = await self._payment_repo.get_by_id(payment_id)
        if payment is None:
            raise PaymentNotFoundError(str(payment_id))
        return payment

    async def apply_payment_result(self, payment_id: UUID, success: bool) -> Payment:
        """
        Применить результат обработки платежа во внешнем шлюзе.

        Вызывается после того, как consumer получил ответ от платёжного
        шлюза (или его эмуляции) — сам переход статуса остаётся правилом
        домена (Payment.mark_succeeded/mark_failed), а не присваиванием
        поля напрямую в ORM-модели.
        """
        payment = await self._payment_repo.get_by_id(payment_id)
        if payment is None:
            raise PaymentNotFoundError(str(payment_id))

        if success:
            payment.mark_succeeded()
        else:
            payment.mark_failed()

        await self._payment_repo.save(payment)
        logger.info(f"Payment {payment.id} updated to status {payment.status.value}")
        return payment