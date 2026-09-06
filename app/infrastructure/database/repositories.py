from datetime import datetime, timezone
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.entities import Currency, Payment, PaymentStatus
from app.services.repositories import OutboxRepository, PaymentRepository
from app.infrastructure.database.models import OutboxModel, PaymentModel


class SQLAlchemyPaymentRepository(PaymentRepository):
    """
    Адаптер: реализация PaymentRepository через SQLAlchemy.

    Отвечает за маппинг между доменной сущностью Payment
    и ORM моделью PaymentModel.
    """

    def __init__(self, session: AsyncSession):
        self._session = session

    async def save(self, payment: Payment) -> None:
        """Сохранить платёж (upsert)."""
        existing = await self._session.get(PaymentModel, payment.id)

        if existing:
            # Обновляем существующую запись
            existing.amount = payment.amount
            existing.currency = payment.currency.value
            existing.description = payment.description
            existing.webhook_url = payment.webhook_url
            existing.status = payment.status.value
            existing.metadata_ = payment.metadata
            existing.idempotency_key = payment.idempotency_key
        else:
            # Создаём новую запись
            db_model = PaymentModel(
                id=payment.id,
                amount=payment.amount,
                currency=payment.currency.value,
                description=payment.description,
                webhook_url=payment.webhook_url,
                status=payment.status.value,
                metadata_=payment.metadata,
                idempotency_key=payment.idempotency_key,
            )
            self._session.add(db_model)

        await self._session.flush()

    async def get_by_id(self, payment_id: UUID) -> Payment | None:
        """Получить платёж по ID."""
        db_model = await self._session.get(PaymentModel, payment_id)
        if db_model is None:
            return None
        return self._to_domain(db_model)

    async def get_by_idempotency_key(self, key: str) -> Payment | None:
        """Получить платёж по idempotency key."""
        stmt = select(PaymentModel).where(
            PaymentModel.idempotency_key == key
        )
        result = await self._session.execute(stmt)
        db_model = result.scalar_one_or_none()
        if db_model is None:
            return None
        return self._to_domain(db_model)

    @staticmethod
    def _to_domain(model: PaymentModel) -> Payment:
        """Маппинг: ORM модель -> доменная сущность."""
        return Payment(
            id=model.id,
            amount=model.amount,
            currency=Currency(model.currency),
            description=model.description,
            webhook_url=model.webhook_url,
            status=PaymentStatus(model.status),
            metadata=model.metadata_ or {},
            idempotency_key=model.idempotency_key,
            created_at=model.created_at,
        )


class SQLAlchemyOutboxRepository(OutboxRepository):
    """
    Адаптер: реализация OutboxRepository через SQLAlchemy.
    """

    def __init__(self, session: AsyncSession):
        self._session = session

    async def save_event(self, event_type: str, payload: dict) -> None:
        """Сохранить событие в outbox."""
        outbox_entry = OutboxModel(
            event_type=event_type,
            payload=payload,
            status="pending",
        )
        self._session.add(outbox_entry)
        await self._session.flush()

    async def get_pending_events(self, limit: int = 100) -> list[dict]:
        """Получить необработанные события из outbox."""
        stmt = (
            select(OutboxModel)
            .where(OutboxModel.status == "pending")
            .order_by(OutboxModel.created_at.asc())
            .limit(limit)
        )
        result = await self._session.execute(stmt)
        rows = result.scalars().all()

        return [
            {
                "id": row.id,
                "event_type": row.event_type,
                "payload": row.payload,
                "created_at": row.created_at.isoformat(),
            }
            for row in rows
        ]

    async def mark_processed(self, event_id: UUID) -> None:
        """Отметить событие как обработанное."""
        stmt = (
            update(OutboxModel)
            .where(OutboxModel.id == event_id)
            .values(
                status="processed",
                processed_at=datetime.now(timezone.utc),
            )
        )
        await self._session.execute(stmt)
        await self._session.flush()