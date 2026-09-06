from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Настройки приложения. Читаются из .env файла и переменных окружения."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # --- App ---
    app_name: str = "Payment Service"
    debug: bool = False

    # --- Database ---
    db_host: str = "localhost"
    db_port: int = 5432
    db_user: str = "postgres"
    db_password: str = "postgres"
    db_name: str = "payments"

    @property
    def database_url(self) -> str:
        """Async URL для SQLAlchemy (psycopg v3)."""
        return (
            f"postgresql+psycopg://{self.db_user}:{self.db_password}"
            f"@{self.db_host}:{self.db_port}/{self.db_name}"
        )

    @property
    def database_url_sync(self) -> str:
        """Для Alembic (синхронный драйвер psycopg v3)."""
        return (
            f"postgresql+psycopg://{self.db_user}:{self.db_password}"
            f"@{self.db_host}:{self.db_port}/{self.db_name}"
        )

    # --- RabbitMQ ---
    rabbit_host: str = "localhost"
    rabbit_port: int = 5672
    rabbit_user: str = "guest"
    rabbit_password: str = "guest"

    @property
    def rabbit_url(self) -> str:
        return (
            f"amqp://{self.rabbit_user}:{self.rabbit_password}"
            f"@{self.rabbit_host}:{self.rabbit_port}/"
        )

    # --- Auth ---
    api_key: str = "super-secret-api-key"

    # --- Business logic ---
    payment_processing_min_sec: float = 2.0
    payment_processing_max_sec: float = 5.0
    payment_success_rate: float = 0.9  # 90% успех, 10% ошибка


settings = Settings()