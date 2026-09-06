import pytest
from unittest.mock import AsyncMock

from app.services.repositories import OutboxRepository, PaymentRepository
from app.services.services import PaymentService


@pytest.fixture
def mock_payment_repo():
    """Мок репозитория платежей."""
    repo = AsyncMock()
    # Явно определяем методы как async
    repo.save = AsyncMock()
    repo.get_by_id = AsyncMock()
    repo.get_by_idempotency_key = AsyncMock()
    return repo


@pytest.fixture
def mock_outbox_repo():
    """Мок репозитория outbox."""
    repo = AsyncMock()
    repo.save_event = AsyncMock()
    repo.get_pending_events = AsyncMock()
    repo.mark_processed = AsyncMock()
    return repo


@pytest.fixture
def payment_service(mock_payment_repo, mock_outbox_repo):
    """PaymentService с моками репозиториев."""
    return PaymentService(mock_payment_repo, mock_outbox_repo)