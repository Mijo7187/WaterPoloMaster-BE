import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any, Optional

from pydantic import ConfigDict, Field, model_validator

from app.common.crud.crud_schemas import (
    CrudCreateSchema,
    CrudFilters,
    CrudResponseSchema,
    CrudUpdateSchema,
)
from app.features.contract_installment.contract_installment_schemas import (
    ContractInstallmentListResponse,
)
from app.features.payment.payment_model import PayableType, PaymentStatus, PaymentTypeCode
from app.features.tournament.tournament_schemas import TournamentListResponse
from app.features.training.training_schemas import TrainingListResponse
from app.features.wallet.wallet_schemas import WalletResponse


# Which schema serializes a resolved payable, keyed by its type. Mirrors the
# resolver's registry — adding a payable type means adding a line to both.
PAYABLE_RESPONSE_SCHEMAS = {
    PayableType.CONTRACT_INSTALLMENT: ContractInstallmentListResponse,
    PayableType.TOURNAMENT: TournamentListResponse,
    PayableType.TRAINING: TrainingListResponse,
}


class PaymentCreate(CrudCreateSchema):
    sender_wallet_id: uuid.UUID
    receiver_wallet_id: uuid.UUID
    payment_type: PaymentTypeCode
    amount: Decimal = Field(..., gt=0, decimal_places=2)
    status: PaymentStatus = PaymentStatus.PENDING
    description: Optional[str] = None

    # Polymorphic payable. Structural pairing is checked here; the rules about
    # WHICH payable type a given payment_type demands — and whether the target
    # row actually exists — live in PaymentService.create() against
    # PAYMENT_TYPE_SPECS, because payable_id has no DB foreign key to lean on.
    payable_type: Optional[PayableType] = None
    payable_id: Optional[int] = None

    @model_validator(mode="after")
    def _payable_pair_is_complete(self) -> "PaymentCreate":
        if (self.payable_type is None) != (self.payable_id is None):
            raise ValueError(
                "payable_type and payable_id must be provided together."
            )
        return self


class PaymentUpdate(CrudUpdateSchema):
    status: Optional[PaymentStatus] = None
    description: Optional[str] = None


class PaymentResponse(CrudResponseSchema):
    id: uuid.UUID
    sender_wallet_id: uuid.UUID
    receiver_wallet_id: uuid.UUID
    payment_type: PaymentTypeCode
    amount: Decimal
    status: PaymentStatus
    description: Optional[str] = None
    payable_type: Optional[PayableType] = None
    payable_id: Optional[int] = None
    created_at: Optional[datetime] = None
    sender_wallet: Optional[WalletResponse] = None
    receiver_wallet: Optional[WalletResponse] = None

    # Populated by the batch resolver before serialization. Typed loosely
    # because the concrete shape depends on payable_type; the validator below
    # narrows it to the right schema.
    payable: Optional[Any] = None

    model_config = ConfigDict(from_attributes=True)

    @model_validator(mode="after")
    def _serialize_payable(self) -> "PaymentResponse":
        """Turn the raw resolved ORM payable into its list-schema dict.

        A payable that was never resolved, or whose target has been deleted
        (orphan), stays None — a dangling reference must not break the list.
        """
        if self.payable is None or isinstance(self.payable, dict):
            return self

        schema = PAYABLE_RESPONSE_SCHEMAS.get(self.payable_type)
        if schema is None:
            self.payable = None
            return self

        self.payable = schema.model_validate(self.payable).model_dump()
        return self


class PaymentFilters(CrudFilters):
    wallet_id: Optional[uuid.UUID] = None
    sender_wallet_id: Optional[uuid.UUID] = None
    receiver_wallet_id: Optional[uuid.UUID] = None
    payment_type: Optional[PaymentTypeCode] = None
    status: Optional[PaymentStatus] = None
    amount__gte: Optional[Decimal] = None
    amount__lte: Optional[Decimal] = None
    payable_type: Optional[PayableType] = None
    payable_id: Optional[int] = None
