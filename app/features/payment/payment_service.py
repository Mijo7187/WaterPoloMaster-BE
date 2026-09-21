import uuid
from typing import Any, List, Optional

from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.common.crud.crud_service import CrudService
from app.common.resolver.polymorphic_resolver import payable_model_for, resolve_payables
from app.core.api.exceptions import BadRequestException, ForbiddenException, NotFoundException
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


def validate_payment_context(
    spec: PaymentTypeSpec, schema: PaymentCreate, db: Session
) -> None:
    """Guard the polymorphic payable reference.

    `payable_id` deliberately has no DB foreign key, so this is the integrity
    check that replaces it. Two rules:

      1. The payable_type must be exactly what the payment type requires per
         PAYMENT_TYPE_SPECS — and a type that requires none must not carry one.
      2. The referenced row must actually exist.
    """
    required = spec.required_context

    if required is None:
        if schema.payable_type is not None:
            raise BadRequestException(
                f"Payment type '{schema.payment_type.value}' is ad-hoc and must not "
                f"reference a payable; got '{schema.payable_type.value}'."
            )
        return

    if schema.payable_type is None:
        raise BadRequestException(
            f"Payment type '{schema.payment_type.value}' requires a payable of type "
            f"'{required.value}'."
        )

    if schema.payable_type != required:
        raise BadRequestException(
            f"Payment type '{schema.payment_type.value}' requires payable_type "
            f"'{required.value}', got '{schema.payable_type.value}'."
        )

    model = payable_model_for(schema.payable_type)
    if model is None:
        raise BadRequestException(
            f"Unknown payable type '{schema.payable_type.value}'."
        )

    exists = (
        db.query(model.id).filter(model.id == schema.payable_id).first() is not None
    )
    if not exists:
        raise NotFoundException(
            f"No {schema.payable_type.value} with id {schema.payable_id}."
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

    def create(self, schema: PaymentCreate, current_user: Optional[Any] = None) -> Payment:
        # schema.payment_type is a PaymentTypeCode enum; validity is guaranteed
        # by Pydantic, so the spec lookup can't miss.
        spec = PAYMENT_TYPE_SPECS[schema.payment_type]

        sender_wallet = self.db.get(Wallet, schema.sender_wallet_id)
        if not sender_wallet:
            raise NotFoundException("Sender wallet not found")

        receiver_wallet = self.db.get(Wallet, schema.receiver_wallet_id)
        if not receiver_wallet:
            raise NotFoundException("Receiver wallet not found")

        company_id = self.company_scope_for(current_user)
        if company_id is not None and not (
            self.repository.wallet_in_company(sender_wallet.id, company_id)
            or self.repository.wallet_in_company(receiver_wallet.id, company_id)
        ):
            raise ForbiddenException("You can only create payments involving your own company.")

        validate_payment_wallets(
            spec, schema.payment_type.value, sender_wallet, receiver_wallet
        )
        validate_payment_context(spec, schema, self.db)

        return self.repository.create(schema.model_dump())

    def get_list(self, filters, company_id: Optional[int] = None) -> tuple[List[Payment], int]:
        """List payments with every payable resolved in one batched pass per
        type — bounded query count regardless of page size."""
        items, total = self.repository.get_list(filters, company_id=company_id)
        resolve_payables(self.db, items)
        return items, total

    def get_by_id(self, obj_id: uuid.UUID, company_id: Optional[int] = None) -> Payment:
        obj = super().get_by_id(obj_id, company_id=company_id)
        resolve_payables(self.db, [obj])
        return obj

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
        resolve_payables(self.db, [obj])
        return obj
