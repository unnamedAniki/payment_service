from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from app.infrastructure.outbox.worker import OutboxWorker


class TestOutboxWorker:
    """Тесты Outbox Worker."""

    @patch("app.infrastructure.outbox.worker.SQLAlchemyOutboxRepository")
    @patch("app.infrastructure.outbox.worker.async_session_factory")
    @patch("app.infrastructure.outbox.worker.RabbitMQPublisher")
    async def test_process_batch_no_events(
        self, mock_publisher_class, mock_session_factory, mock_repo_class
    ):
        """Обработка батча без событий."""
        mock_session = AsyncMock()
        mock_session_factory.return_value.__aenter__.return_value = mock_session

        mock_repo = AsyncMock()
        mock_repo.get_pending_events.return_value = []
        mock_repo_class.return_value = mock_repo

        mock_publisher = AsyncMock()
        mock_publisher_class.return_value = mock_publisher

        worker = OutboxWorker()
        worker._publisher = mock_publisher

        await worker._process_batch()

        mock_publisher.publish.assert_not_called()

    @patch("app.infrastructure.outbox.worker.SQLAlchemyOutboxRepository")
    @patch("app.infrastructure.outbox.worker.async_session_factory")
    @patch("app.infrastructure.outbox.worker.RabbitMQPublisher")
    async def test_process_batch_with_events(
        self, mock_publisher_class, mock_session_factory, mock_repo_class
    ):
        """Обработка батча с событиями."""
        event_id = uuid4()
        event = {
            "id": event_id,
            "event_type": "payment.created",
            "payload": {"payment_id": "123"},
            "created_at": datetime.now(timezone.utc).isoformat(),
        }

        mock_session = AsyncMock()
        mock_session_factory.return_value.__aenter__.return_value = mock_session

        mock_repo = AsyncMock()
        mock_repo.get_pending_events.return_value = [event]
        mock_repo_class.return_value = mock_repo

        mock_publisher = AsyncMock()
        mock_publisher_class.return_value = mock_publisher

        worker = OutboxWorker()
        worker._publisher = mock_publisher

        await worker._process_batch()

        mock_publisher.publish.assert_called_once_with(
            routing_key="payment.created",
            payload={"payment_id": "123"},
            message_id=str(event_id),
        )
        mock_repo.mark_processed.assert_called_once_with(event_id)
        mock_session.commit.assert_called_once()

    @patch("app.infrastructure.outbox.worker.async_session_factory")
    @patch("app.infrastructure.outbox.worker.RabbitMQPublisher")
    async def test_process_event_publish_failure(
        self, mock_publisher_class, mock_session_factory
    ):
        """Ошибка публикации — событие остаётся pending."""
        event_id = uuid4()
        event = {
            "id": event_id,
            "event_type": "payment.created",
            "payload": {"payment_id": "123"},
            "created_at": datetime.now(timezone.utc).isoformat(),
        }

        mock_session = AsyncMock()
        mock_session_factory.return_value.__aenter__.return_value = mock_session

        mock_repo = AsyncMock()

        mock_publisher = AsyncMock()
        mock_publisher.publish.side_effect = Exception("RabbitMQ error")
        mock_publisher_class.return_value = mock_publisher

        worker = OutboxWorker()
        worker._publisher = mock_publisher

        with pytest.raises(Exception, match="RabbitMQ error"):
            await worker._process_event(mock_repo, mock_session, event)

        mock_repo.mark_processed.assert_not_called()
        mock_session.commit.assert_not_called()