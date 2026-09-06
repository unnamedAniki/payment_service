# Payment Service

Асинхронный микросервис для обработки платежей, реализованный в соответствии с принципами **чистой/слоистой архитектуры**.

Сервис принимает запросы на оплату, обрабатывает их через эмулируемый платёжный шлюз и уведомляет клиента о результате через webhook.

---

## Архитектура

Проект построен по принципу **Clean Architecture** с разделением на слои:

- **API Layer (FastAPI)**
    - HTTP endpoints (`POST /api/v1/payments`, `GET /api/v1/payments/{id}`)
    - Auth middleware через заголовок `X-API-Key`
    - Request/Response DTO на Pydantic v2
    - Dependency Injection для сервисов и сессий

- **Services Layer (Business Logic)**
    - Entities — доменная сущность `Payment`
    - Services — use-cases (`PaymentService`)
    - Repository interfaces (порты) — абстрактные контракты
    - Domain exceptions — бизнес-исключения

- **Infrastructure Layer**
    - Database — SQLAlchemy 2.0 async + PostgreSQL + Alembic
    - Broker — RabbitMQ через FastStream (consumer) и aio-pika (publisher)
    - Outbox Worker — фоновый процесс для гарантированной доставки событий

**Ключевые принципы:**

- **Dependency Inversion** — сервисный слой зависит только от абстракций (портов)
- **Transactional Outbox** — гарантия доставки событий
- **Idempotency** — защита от дублирования платежей
- **Retry + DLQ** — надёжная обработка сбоев

---

## Стек технологий

| Компонент         | Технология                        |
|-------------------|-----------------------------------|
| Web Framework     | FastAPI + Pydantic v2             |
| ORM               | SQLAlchemy 2.0 (async)            |
| Database          | PostgreSQL 16                     |
| Migrations        | Alembic                           |
| Message Broker    | RabbitMQ + FastStream + aio-pika  |
| HTTP Client       | httpx (для webhook)               |
| Containerization  | Docker + docker-compose           |
| Python            | 3.11+                             |
| Testing           | pytest + pytest-asyncio           |
---

## Структура проекта

- `test_task/`
    - `app/`
        - `api/` — Слой представления (HTTP)
            - `routes/payments.py` — Endpoints: POST/GET payments
            - `deps.py` — Dependency Injection
            - `router.py` — Объединение роутеров
        - `services/` — Бизнес-логика (ядро)
            - `entities.py` — Доменная сущность Payment
            - `exceptions.py` — Доменные исключения
            - `repositories.py` — Порты (абстрактные интерфейсы)
            - `services.py` — Use-cases (PaymentService)
        - `infrastructure/` — Внешние зависимости
            - `database/`
                - `models.py` — ORM модели (PaymentModel, OutboxModel)
                - `repositories.py` — Адаптеры (SQLAlchemy реализации)
                - `session.py` — Async engine + sessionmaker
            - `broker/`
                - `publisher.py` — Публикация в RabbitMQ (aio-pika)
                - `consumer.py` — FastStream consumer + webhook
            - `outbox/`
                - `worker.py` — Outbox Worker (polling)
        - `schemas/` — Pydantic DTO
            - `payments.py` — Request/Response схемы
        - `core/` — Конфигурация
            - `config.py` — Settings (pydantic-settings)
            - `security.py` — Auth (X-API-Key)
        - `main.py` — FastAPI приложение
        - `worker.py` — Точка входа для consumer
    - `alembic/` — Миграции БД
    - `docker-compose.yml` — Полный стек
    - `Dockerfile` — Универсальный образ
    - `requirements.txt` — Зависимости
    - `.env` — Переменные окружения
    - `tests/` — Тесты
        - `unit/` — Unit-тесты (с моками)
        - `integration/` — Интеграционные тесты API
---

## Быстрый старт (Docker)

### 1. Перейти в папку проекта

    cd payment-service

### 2. Создать `.env` файл (опционально, есть дефолты)

    API_KEY=super-secret-api-key

### 3. Запустить весь стек

    docker-compose up --build

Будут запущены:

- **PostgreSQL** на `localhost:5432`
- **RabbitMQ** на `localhost:5672` (Management UI: `http://localhost:15672`, guest/guest)
- **Migrations** (one-shot, применяет Alembic миграции)
- **API** на `http://localhost:8000`
- **Outbox Worker** (фоновый процесс)
- **Consumer** (FastStream)

### 4. Проверить работоспособность

    curl http://localhost:8000/health
    # {"status":"ok"}

### 5. Swagger UI

Откройте в браузере: **http://localhost:8000/docs**

---

## Локальный запуск (без Docker)

### Требования

- Python 3.11+
- PostgreSQL 16
- RabbitMQ 3.x

### 1. Установить зависимости

    python -m venv venv
    venv\Scripts\activate     # Windows
    pip install -r requirements.txt

### 2. Настроить `.env`

    DB_HOST=localhost
    DB_PORT=5432
    DB_USER=postgres
    DB_PASSWORD=postgres
    DB_NAME=payments

    RABBIT_HOST=localhost
    RABBIT_PORT=5672
    RABBIT_USER=guest
    RABBIT_PASSWORD=guest

    API_KEY=super-secret-api-key

### 3. Применить миграции

    alembic upgrade head

### 4. Запустить сервисы (в разных терминалах)

    # Терминал 1: API
    uvicorn app.main:app --reload

    # Терминал 2: Outbox Worker
    python -m app.infrastructure.outbox.worker

    # Терминал 3: Consumer
    python -m app.worker

---

## API Endpoints

### Аутентификация

Все endpoints требуют заголовок `X-API-Key`:

    X-API-Key: super-secret-api-key

### 1. Создание платежа

    curl -X POST http://localhost:8000/api/v1/payments \
      -H "Content-Type: application/json" \
      -H "X-API-Key: super-secret-api-key" \
      -H "Idempotency-Key: unique-order-123" \
      -d '{
        "amount": 100.50,
        "currency": "RUB",
        "description": "Оплата заказа #12345",
        "webhook_url": "https://webhook.site/your-unique-url",
        "metadata": {
          "order_id": "12345",
          "customer_email": "test@example.com"
        }
      }'

**Ответ (202 Accepted):**

    {
      "payment_id": "550e8400-e29b-41d4-a716-446655440000",
      "status": "pending",
      "created_at": "2026-09-05T12:34:56.789Z"
    }

### 2. Получение информации о платеже

    curl http://localhost:8000/api/v1/payments/550e8400-e29b-41d4-a716-446655440000 \
      -H "X-API-Key: super-secret-api-key"

**Ответ (200 OK):**

    {
      "id": "550e8400-e29b-41d4-a716-446655440000",
      "amount": 100.50,
      "currency": "RUB",
      "description": "Оплата заказа #12345",
      "webhook_url": "https://webhook.site/your-unique-url",
      "status": "succeeded",
      "metadata": {
        "order_id": "12345",
        "customer_email": "test@example.com"
      },
      "idempotency_key": "unique-order-123",
      "created_at": "2026-09-05T12:34:56.789Z"
    }

---

## Как работает обработка платежа

1. Клиент отправляет `POST /api/v1/payments`
2. API создаёт платёж со статусом `pending` и пишет событие в таблицу `outbox` в **одной транзакции**
3. API возвращает `202 Accepted` с `payment_id`
4. **Outbox Worker** (каждую 1 сек) читает `pending` события из outbox и публикует их в RabbitMQ
5. **Consumer** получает сообщение из очереди `payments.new`
6. Consumer эмулирует обработку платежа (2-5 сек, 90% успех, 10% ошибка)
7. Consumer обновляет статус платежа в БД (`succeeded` или `failed`)
8. Consumer отправляет webhook-уведомление на `webhook_url` клиента
9. При ошибке — **retry** (3 попытки с экспоненциальной задержкой)
10. После 3 неудач — сообщение попадает в **Dead Letter Queue** (`payments.new.dlq`)

---

## 🛡️ Реализованные паттерны

### Transactional Outbox

- Платёж и событие в outbox записываются в **одной транзакции**
- Это гарантирует, что каждый созданный платёж породит событие для публикации
- Outbox Worker обеспечивает надёжную доставку даже при сбоях

### Idempotency

- Заголовок `Idempotency-Key` защищает от дублирования платежей
- Если ключ уже использован — возвращается существующий платёж
- В БД есть уникальный индекс на `idempotency_key`

### Retry с экспоненциальной задержкой

- FastStream автоматически повторяет обработку 3 раза
- Задержка между попытками нарастает экспоненциально
- Применяется как к обработке платежа, так и к отправке webhook

### Dead Letter Queue

- Сообщения, которые не удалось обработать после 3 попыток, попадают в очередь `payments.new.dlq`
- Предназначена для ручной обработки или анализа упавших сообщений

---

## Чек-лист соответствия ТЗ

| Требование                                   | Статус | Реализация                                              |
|----------------------------------------------|:------:|-----------------------------------------------------------|
| Модели и миграции (payments + outbox)        | ✅     | `infrastructure/database/models.py` + Alembic             |
| API: создание платежа (POST)                 | ✅     | `api/routes/payments.py` → 202 Accepted                   |
| API: получение платежа (GET)                 | ✅     | `api/routes/payments.py` → 200 OK                         |
| Consumer с эмуляцией обработки               | ✅     | `infrastructure/broker/consumer.py`                       |
| Outbox pattern                               | ✅     | `infrastructure/outbox/worker.py` + `publisher.py`        |
| Idempotency key                              | ✅     | `domain/services.py` + unique index в БД                  |
| Retry (3 попытки, экспоненциальная задержка) | ✅     | FastStream `retry=3`                                      |
| Dead Letter Queue                            | ✅     | `payments.new.dlq` + dead_letter_exchange                 |
| Webhook уведомление                          | ✅     | `httpx.AsyncClient` в consumer                            |
| Auth (X-API-Key)                             | ✅     | `core/security.py` + `Depends(verify_api_key)`            |
| Docker + docker-compose                      | ✅     | `Dockerfile` + `docker-compose.yml` (6 сервисов)          |
| Чистая/слоистая архитектура                  | ✅     | api / domain / infrastructure / schemas / core            |
| SQLAlchemy 2.0 async                         | ✅     | `psycopg[binary]` + `AsyncSession`                        |
| FastAPI + Pydantic v2                        | ✅     | `model_config`, `field_validator`                         |
| RabbitMQ + FastStream                        | ✅     | Topic exchange, durable queues                            |
| Alembic миграции                             | ✅     | `alembic/` + автогенерация                                |

---

## Полезные команды

    # Посмотреть логи всех сервисов
    docker-compose logs -f

    # Посмотреть логи конкретного сервиса
    docker-compose logs -f api
    docker-compose logs -f consumer
    docker-compose logs -f outbox-worker

    # Перезапустить только API
    docker-compose restart api

    # Остановить весь стек
    docker-compose down

    # Остановить и удалить volumes (очистить БД)
    docker-compose down -v

    # Создать новую миграцию
    alembic revision --autogenerate -m "description"

    # Применить миграции
    alembic upgrade head

    # Откатить последнюю миграцию
    alembic downgrade -1

---

## Тестирование webhook

Для тестирования webhook удобно использовать:

- **https://webhook.site** — мгновенный уникальный URL
- **https://requestbin.com** — альтернатива
- **ngrok** — прокинуть локальный сервер в интернет

Пример с webhook.site:

1. Зайти на https://webhook.site
2. Скопировать уникальный URL
3. Использовать его как `webhook_url` при создании платежа
4. Наблюдать за входящими запросами в браузере

---

## Тестирование

Проект покрыт **unit** и **интеграционными** тестами. Все тесты работают **без Docker, без PostgreSQL, без RabbitMQ** — используются моки и `unittest.mock`.

### Установка зависимостей для тестов

```bash
pip install pytest pytest-asyncio pytest-cov
```
### Команды запуска
#### Все тесты
```bash
pytest -v
```
#### Только unit-тесты
```bash
pytest tests/unit -v
```
#### Только интеграционные тесты
```bash
pytest tests/integration -v
```
#### Конкретный файл
```bash
pytest tests/unit/test_entities.py -v
```
#### Конкретный тест
```bash
pytest tests/unit/test_entities.py::TestPaymentCreate::test_create_payment_defaults -v
```
#### С подробным выводом ошибок
```bash
pytest -v --tb=short
```
#### С отчётом о покрытии кода
```bash
pytest --cov=app --cov-report=term-missing
```
### Структура тестов

- **`tests/unit/`** — unit-тесты для изолированных компонентов
    - `test_entities.py` — доменная сущность `Payment`
    - `test_services.py` — `PaymentService` (use-cases)
    - `test_schemas.py` — Pydantic DTO (валидация)
    - `test_security.py` — проверка API ключа
    - `test_consumer.py` — FastStream consumer + webhook
    - `test_publisher.py` — RabbitMQ publisher
    - `test_outbox_worker.py` — Outbox Worker
- **`tests/integration/`** — интеграционные тесты HTTP-слоя
    - `test_api.py` — endpoints API (POST/GET, auth, валидация)

### Что покрывают тесты

| Файл | Что тестирует | Кол-во тестов |
|------|---------------|:-------------:|
| `test_entities.py` | Создание платежа, переходы статусов, `is_terminal` | 8 |
| `test_services.py` | Создание платежа, idempotency, получение платежа | 7 |
| `test_schemas.py` | Валидация Pydantic схем (валюты, суммы, URL) | 12 |
| `test_security.py` | Проверка API ключа (валидный, неверный, отсутствует) | 4 |
| `test_consumer.py` | Эмуляция обработки, webhook, обновление статуса | 8 |
| `test_publisher.py` | Подключение к RabbitMQ, публикация сообщений | 4 |
| `test_outbox_worker.py` | Обработка батчей событий из outbox | 3 |
| `test_api.py` | HTTP endpoints, auth, валидация, 404/422 | 16 |
| **Итого** | | **62** |

### Ключевые сценарии

- **Создание платежа** — успешное создание, идемпотентность, валидация
- **Получение платежа** — 200 OK, 404 Not Found, невалидный UUID
- **Аутентификация** — отсутствие ключа (401), неверный ключ (401)
- **Валидация** — отрицательная сумма, неподдерживаемая валюта, невалидный URL
- **Retry логика** — успех/неуспех эмуляции, ошибки webhook
- **Outbox** — публикация событий, обработка ошибок RabbitMQ

### Фикстуры

Общие фикстуры находятся в `tests/conftest.py`:

- `mock_payment_repo` — мок репозитория платежей
- `mock_outbox_repo` — мок репозитория outbox
- `payment_service` — `PaymentService` с моками
- `client` — HTTP клиент для интеграционных тестов
- `sample_payment` — образец платежа
- `api_headers` — заголовки с валидным API ключом