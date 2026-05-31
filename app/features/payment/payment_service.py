import uuid

from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.common.crud.crud_service import CrudService
from app.core.api.exceptions import BadRequestException, NotFoundException
from app.features.payment.payment_model import Payment, PaymentStatus
from app.features.payment.payment_repository import PaymentRepository
from app.features.payment.payment_schemas import PaymentCreate
from app.features.sifarnici.payment_type.payment_type_model import PaymentType
from app.features.wallet.wallet_model import Wallet


_ALLOWED_TRANSITIONS: dict[PaymentStatus, set[PaymentStatus]] = {
    PaymentStatus.PENDING: {PaymentStatus.COMPLETED, PaymentStatus.FAILED},
}


def validate_payment_wallets(
    payment_type: PaymentType,
    sender_wallet: Wallet,
    receiver_wallet: Wallet,
) -> None:
    if sender_wallet.owner_type != payment_type.sender_type:
        raise BadRequestException(
            f"Sender wallet owner_type '{sender_wallet.owner_type}' does not match "
            f"required '{payment_type.sender_type}' for payment type '{payment_type.code}'"
        )
    if receiver_wallet.owner_type != payment_type.receiver_type:
        raise BadRequestException(
            f"Receiver wallet owner_type '{receiver_wallet.owner_type}' does not match "
            f"required '{payment_type.receiver_type}' for payment type '{payment_type.code}'"
        )


class PaymentService(CrudService[Payment]):
    def __init__(self, db: Session):
        super().__init__(db, PaymentRepository(db))

    def create(self, schema: PaymentCreate) -> Payment:
        payment_type = self.db.get(PaymentType, schema.payment_type_id)
        if not payment_type:
            raise NotFoundException("PaymentType not found")

        sender_wallet = self.db.get(Wallet, schema.sender_wallet_id)
        if not sender_wallet:
            raise NotFoundException("Sender wallet not found")

        receiver_wallet = self.db.get(Wallet, schema.receiver_wallet_id)
        if not receiver_wallet:
            raise NotFoundException("Receiver wallet not found")

        validate_payment_wallets(payment_type, sender_wallet, receiver_wallet)

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
