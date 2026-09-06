from app.services.exceptions import PaymentNotFoundError


class TestHealthCheck:
    """Тесты health check endpoint."""

    async def test_health_check(self, client):
        """Health check возвращает 200."""
        response = await client.get("/health")

        assert response.status_code == 200
        assert response.json() == {"status": "ok"}


class TestCreatePayment:
    """Тесты POST /api/v1/payments."""

    async def test_create_payment_success(
        self, client, mock_payment_service, api_headers, sample_payment_payload, sample_payment
    ):
        """Успешное создание платежа возвращает 202."""
        mock_payment_service.create_payment.return_value = sample_payment

        response = await client.post(
            "/api/v1/payments",
            json=sample_payment_payload,
            headers=api_headers,
        )

        assert response.status_code == 202
        data = response.json()
        assert "payment_id" in data
        assert data["status"] == "pending"
        assert "created_at" in data

    async def test_create_payment_without_api_key(self, client, sample_payment_payload):
        """Запрос без API ключа возвращает 401."""
        response = await client.post(
            "/api/v1/payments",
            json=sample_payment_payload,
            headers={"Content-Type": "application/json"},
        )

        assert response.status_code == 401

    async def test_create_payment_invalid_api_key(self, client, sample_payment_payload):
        """Запрос с неверным API ключом возвращает 401."""
        response = await client.post(
            "/api/v1/payments",
            json=sample_payment_payload,
            headers={
                "X-API-Key": "wrong-key",
                "Content-Type": "application/json",
            },
        )

        assert response.status_code == 401

    async def test_create_payment_with_idempotency_key(
        self, client, mock_payment_service, api_headers, sample_payment_payload, sample_payment
    ):
        """Idempotency key передаётся в сервис."""
        mock_payment_service.create_payment.return_value = sample_payment

        headers = {**api_headers, "Idempotency-Key": "unique-key-123"}
        response = await client.post(
            "/api/v1/payments",
            json=sample_payment_payload,
            headers=headers,
        )

        assert response.status_code == 202
        call_kwargs = mock_payment_service.create_payment.call_args.kwargs
        assert call_kwargs["idempotency_key"] == "unique-key-123"

    async def test_create_payment_missing_required_fields(self, client, api_headers):
        """Запрос без обязательных полей возвращает 422."""
        response = await client.post(
            "/api/v1/payments",
            json={"amount": 100.00},
            headers=api_headers,
        )

        assert response.status_code == 422

    async def test_create_payment_invalid_currency(self, client, api_headers):
        """Невалидная валюта возвращает 422."""
        payload = {
            "amount": 100.00,
            "currency": "GBP",
            "description": "Test",
            "webhook_url": "https://example.com/webhook",
        }

        response = await client.post(
            "/api/v1/payments",
            json=payload,
            headers=api_headers,
        )

        assert response.status_code == 422

    async def test_create_payment_negative_amount(self, client, api_headers):
        """Отрицательная сумма возвращает 422."""
        payload = {
            "amount": -10.00,
            "currency": "RUB",
            "description": "Test",
            "webhook_url": "https://example.com/webhook",
        }

        response = await client.post(
            "/api/v1/payments",
            json=payload,
            headers=api_headers,
        )

        assert response.status_code == 422


class TestGetPayment:
    """Тесты GET /api/v1/payments/{payment_id}."""

    async def test_get_payment_success(
        self, client, mock_payment_service, api_headers, sample_payment
    ):
        """Успешное получение платежа возвращает 200."""
        mock_payment_service.get_payment.return_value = sample_payment

        response = await client.get(
            f"/api/v1/payments/{sample_payment.id}",
            headers=api_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == str(sample_payment.id)
        assert data["amount"] == "100.50"
        assert data["currency"] == "RUB"
        assert data["status"] == "pending"
        assert data["description"] == "Тестовый платёж"

    async def test_get_payment_not_found(self, client, mock_payment_service, api_headers):
        """Запрос несуществующего платежа возвращает 404."""
        mock_payment_service.get_payment.side_effect = PaymentNotFoundError(
            "00000000-0000-0000-0000-000000000000"
        )

        response = await client.get(
            "/api/v1/payments/00000000-0000-0000-0000-000000000000",
            headers=api_headers,
        )

        assert response.status_code == 404

    async def test_get_payment_without_api_key(self, client):
        """Запрос без API ключа возвращает 401."""
        response = await client.get(
            "/api/v1/payments/00000000-0000-0000-0000-000000000000",
        )

        assert response.status_code == 401

    async def test_get_payment_invalid_uuid(self, client, api_headers):
        """Невалидный UUID возвращает 422."""
        response = await client.get(
            "/api/v1/payments/not-a-uuid",
            headers=api_headers,
        )

        assert response.status_code == 422