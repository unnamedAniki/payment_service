from abc import ABC, abstractmethod
from uuid import UUID

from app.services.entities import Payment


class PaymentRepository(ABC):
    """
    Абстрактный репозиторий платежей.

    Определяет контракт для работы с платежами.
    Реализация находится в infrastructure слое.
    """

    @abstractmethod
    async def save(self, payment: Payment) -> Payment:
        """Сохранить платёж (создание или обновление)."""
        ...

    @abstractmethod
    async def get_by_id(self, payment_id: UUID) -> Payment | None:
        """Получить платёж по ID."""
        ...

    @abstractmethod
    async def get_by_idempotency_key(self, key: str) -> Payment | None:
        """Получить платёж по idempotency key."""
        ...


class OutboxRepository(ABC):
    """
    Абстрактный репозиторий для outbox таблицы.

    Используется для паттерна Transactional Outbox.
    """

    @abstractmethod
    async def save_event(
            self,
            event_type: str,
            payload: dict,
    ) -> None:
        """Сохранить событие в outbox (в рамках транзакции с платежом)."""
        ...

    @abstractmethod
    async def get_pending_events(self, limit: int = 10) -> list[dict]:
        """Получить необработанные события из outbox."""
        ...

    @abstractmethod
    async def mark_processed(self, event_id: UUID) -> None:
        """Отметить событие как обработанное."""
        ...