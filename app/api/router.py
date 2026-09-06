from fastapi import APIRouter

from app.api.routes import payments

# Главный роутер API
api_router = APIRouter()

# Подключаем роутер платежей
api_router.include_router(payments.router)