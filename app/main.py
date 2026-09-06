import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.router import api_router
from app.core.config import settings

# Настраиваем логирование
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Lifecycle события приложения.

    Выполняется при старте и остановке приложения.
    """
    logger.info(f"Starting {settings.app_name}...")
    yield
    logger.info(f"Shutting down {settings.app_name}...")


# Создаём FastAPI приложение
app = FastAPI(
    title=settings.app_name,
    version="1.0.0",
    description="Асинхронный сервис обработки платежей",
    lifespan=lifespan,
)

# Подключаем API роутеры
app.include_router(api_router)


@app.get("/health", tags=["health"])
async def health_check():
    """
    Health check endpoint.

    Используется для проверки работоспособности сервиса.
    """
    return {"status": "ok"}