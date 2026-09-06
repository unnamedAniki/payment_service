import pytest
from fastapi import HTTPException

from app.core.security import verify_api_key


class TestVerifyApiKey:
    """Тесты проверки API ключа."""

    async def test_valid_api_key(self):
        """Валидный API ключ проходит проверку."""
        result = await verify_api_key("super-secret-api-key")
        assert result == "super-secret-api-key"

    async def test_missing_api_key(self):
        """Отсутствие API ключа вызывает 401."""
        with pytest.raises(HTTPException) as exc_info:
            await verify_api_key(None)

        assert exc_info.value.status_code == 401
        assert "Missing API key" in exc_info.value.detail

    async def test_invalid_api_key(self):
        """Неверный API ключ вызывает 401."""
        with pytest.raises(HTTPException) as exc_info:
            await verify_api_key("wrong-key")

        assert exc_info.value.status_code == 401
        assert "Invalid API key" in exc_info.value.detail

    async def test_empty_string_api_key(self):
        """Пустая строка как API ключ вызывает 401."""
        with pytest.raises(HTTPException) as exc_info:
            await verify_api_key("")

        assert exc_info.value.status_code == 401