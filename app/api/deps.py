from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.repositories import OutboxRepository, PaymentRepository
from app.services.services import PaymentService
from app.infrastructure.database.repositories import (
    SQLAlchemyOutboxRepository,
    SQLAlchemyPaymentRepository,
)
from app.infrastructure.database.session import async_session_factory


async def get_session() -> AsyncSession:
    """
    Dependency для FastAPI — получает сессию из пула.
    """
    async with async_session_factory() as session:
        yield session


# Типизированные зависимости через Annotated — FastAPI не будет их валидировать как response
SessionDep = Annotated[AsyncSession, Depends(get_session)]


async def get_payment_service(session: SessionDep) -> PaymentService:
    """
    Создаёт PaymentService с внедрёнными репозиториями.
    """
    payment_repo = SQLAlchemyPaymentRepository(session)
    outbox_repo = SQLAlchemyOutboxRepository(session)
    return PaymentService(payment_repo, outbox_repo)


PaymentServiceDep = Annotated[PaymentService, Depends(get_payment_service)]