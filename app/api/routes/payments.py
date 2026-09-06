import logging
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import PaymentServiceDep, SessionDep
from app.core.security import verify_api_key
from app.services.exceptions import (
    DuplicateIdempotencyKeyError,
    PaymentNotFoundError,
)
from app.services.services import PaymentService
from app.schemas.payments import (
    PaymentCreateRequest,
    PaymentCreateResponse,
    PaymentResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/payments", tags=["payments"])


@router.post(
    "",
    response_model=PaymentCreateResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Создание платежа",
    description="Создаёт новый платёж и возвращает 202 Accepted",
)
async def create_payment(
    request: PaymentCreateRequest,
    session: SessionDep,
    payment_service: PaymentServiceDep,
    idempotency_key: str | None = Header(None, alias="Idempotency-Key"),
    _: str = Depends(verify_api_key),
):
    """Создание платежа."""
    try:
        payment = await payment_service.create_payment(
            amount=request.amount,
            currency=request.currency,
            description=request.description,
            webhook_url=str(request.webhook_url),
            metadata=request.metadata,
            idempotency_key=idempotency_key,
        )

        await session.commit()

        logger.info(f"Payment {payment.id} created successfully")

        return PaymentCreateResponse(
            payment_id=payment.id,
            status=payment.status,
            created_at=payment.created_at,
        )

    except DuplicateIdempotencyKeyError as e:
        await session.rollback()
        logger.warning(f"Duplicate idempotency key: {e.key}")

        existing_payment = await payment_service.get_payment(
            UUID(e.existing_payment_id)
        )

        return PaymentCreateResponse(
            payment_id=existing_payment.id,
            status=existing_payment.status,
            created_at=existing_payment.created_at,
        )

    except Exception as e:
        await session.rollback()
        logger.exception(f"Error creating payment: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        )


@router.get(
    "/{payment_id}",
    response_model=PaymentResponse,
    status_code=status.HTTP_200_OK,
    summary="Получение информации о платеже",
    description="Возвращает детальную информацию о платеже по ID",
)
async def get_payment(
    payment_id: UUID,
    payment_service: PaymentServiceDep,
    _: str = Depends(verify_api_key),
):
    """Получение информации о платеже."""
    try:
        payment = await payment_service.get_payment(payment_id)
        return PaymentResponse.model_validate(payment)

    except PaymentNotFoundError as e:
        logger.warning(f"Payment not found: {e.payment_id}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Payment with id '{payment_id}' not found",
        )

    except Exception as e:
        logger.exception(f"Error getting payment: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        )