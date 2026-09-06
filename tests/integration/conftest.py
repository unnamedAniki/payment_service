from decimal import Decimal
from unittest.mock import AsyncMock

import pytest
from httpx import ASGITransport, AsyncClient

from app.api.deps import get_payment_service, get_session
from app.services.entities import Currency, Payment, PaymentStatus
from app.services.services import PaymentService
from app.main import app


@pytest.fixture
def mock_payment_service():
    """Мок PaymentService для интеграционных тестов."""
    return AsyncMock(spec=PaymentService)


@pytest.fixture
async def client(mock_payment_service):
    """HTTP клиент для тестирования API."""

    async def override_get_session():
        session = AsyncMock()
        yield session

    app.dependency_overrides[get_session] = override_get_session
    app.dependency_overrides[get_payment_service] = lambda: mock_payment_service

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac

    app.dependency_overrides.clear()


@pytest.fixture
def sample_payment():
    """Образец платежа для тестов."""
    return Payment.create(
        amount=Decimal("100.50"),
        currency=Currency.RUB,
        description="Тестовый платёж",
        webhook_url="https://example.com/webhook",
        metadata={"order_id": "12345"},
        idempotency_key="test-key-1",
    )


@pytest.fixture
def api_headers():
    """Заголовки с валидным API ключом."""
    return {
        "X-API-Key": "super-secret-api-key",
        "Content-Type": "application/json",
    }


@pytest.fixture
def sample_payment_payload():
    """Образец тела запроса для создания платежа."""
    return {
        "amount": 100.50,
        "currency": "RUB",
        "description": "Тестовый платёж",
        "webhook_url": "https://example.com/webhook",
        "metadata": {"order_id": "12345"},
    }