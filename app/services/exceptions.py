class DomainError(Exception):
    """Базовое исключение доменного слоя."""
    pass


class PaymentNotFoundError(DomainError):
    """Платёж не найден."""
    def __init__(self, payment_id: str):
        self.payment_id = payment_id
        super().__init__(f"Payment with id '{payment_id}' not found")


class DuplicateIdempotencyKeyError(DomainError):
    """Попытка создать платёж с уже использованным idempotency key."""
    def __init__(self, key: str, existing_payment_id: str):
        self.key = key
        self.existing_payment_id = existing_payment_id
        super().__init__(
            f"Idempotency key '{key}' already used for payment '{existing_payment_id}'"
        )


class InvalidPaymentStateError(DomainError):
    """Недопустимая операция для текущего состояния платежа."""
    def __init__(self, message: str = "Invalid payment state transition"):
        super().__init__(message)


class PaymentProcessingError(DomainError):
    """Ошибка при обработке платежа (эмулирует сбой шлюза)."""
    def __init__(self, payment_id: str):
        self.payment_id = payment_id
        super().__init__(f"Payment processing failed for id '{payment_id}'")