import uuid

from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.common.crud.crud_service import CrudService
from app.core.api.exceptions import BadRequestException, NotFoundException
from app.features.payment.payment_model import (
    PAYMENT_TYPE_SPECS,
    Payment,
    PaymentStatus,
    PaymentTypeSpec,
)
from app.features.payment.payment_repository import PaymentRepository
from app.features.payment.payment_schemas import PaymentCreate
from app.features.wallet.wallet_model import Wallet


_ALLOWED_TRANSITIONS: dict[PaymentStatus, set[PaymentStatus]] = {
    PaymentStatus.PENDING: {PaymentStatus.COMPLETED, PaymentStatus.FAILED},
}


def validate_payment_context(spec: PaymentTypeSpec, schema: PaymentCreate) -> None:
    required = spec.required_context
    if required is not None and getattr(schema, required) is None:
        raise BadRequestException(
            f"Payment type '{schema.payment_type.value}' requires '{required}' to be provided."
        )


def validate_payment_wallets(
    spec: PaymentTypeSpec,
    payment_type: str,
    sender_wallet: Wallet,
    receiver_wallet: Wallet,
) -> None:
    if sender_wallet.owner_type != spec.sender_type:
        raise BadRequestException(
            f"Sender wallet owner_type '{sender_wallet.owner_type}' does not match "
            f"required '{spec.sender_type}' for payment type '{payment_type}'"
        )
    if receiver_wallet.owner_type != spec.receiver_type:
        raise BadRequestException(
            f"Receiver wallet owner_type '{receiver_wallet.owner_type}' does not match "
            f"required '{spec.receiver_type}' for payment type '{payment_type}'"
        )


class PaymentService(CrudService[Payment]):
    def __init__(self, db: Session):
        super().__init__(db, PaymentRepository(db))

    def create(self, schema: PaymentCreate) -> Payment:
        # schema.payment_type is a PaymentTypeCode enum; validity is guaranteed
        # by Pydantic, so the spec lookup can't miss.
        spec = PAYMENT_TYPE_SPECS[schema.payment_type]

        sender_wallet = self.db.get(Wallet, schema.sender_wallet_id)
        if not sender_wallet:
            raise NotFoundException("Sender wallet not found")

        receiver_wallet = self.db.get(Wallet, schema.receiver_wallet_id)
        if not receiver_wallet:
            raise NotFoundException("Receiver wallet not found")

        validate_payment_wallets(
            spec, schema.payment_type.value, sender_wallet, receiver_wallet
        )
        validate_payment_context(spec, schema)

        return self.repository.create(schema.model_dump())

    def update(self, obj_id: uuid.UUID, schema: BaseModel) -> Payment:
        data = schema.model_dump(exclude_unset=True)
        new_status = data.get("status")

        if new_status is not None:
            payment = self.repository.get_by_id(obj_id)
            if not payment:
                raise NotFoundException("Payment not found")
            allowed = _ALLOWED_TRANSITIONS.get(payment.status, set())
            if new_status not in allowed:
                raise BadRequestException(
                    f"Cannot transition payment from '{payment.status}' to '{new_status}'. "
                    f"Allowed: {[s.value for s in allowed] or 'none'}"
                )

        obj = self.repository.update(obj_id, data)
        if not obj:
            raise NotFoundException("Payment not found")
        return obj
