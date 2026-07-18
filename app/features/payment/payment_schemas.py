import uuid
from datetime import datetime
from decimal import Decimal
from typing import Optional

from pydantic import ConfigDict, Field, model_validator

from app.common.crud.crud_schemas import CrudCreateSchema, CrudFilters, CrudResponseSchema, CrudUpdateSchema
from app.features.payment.payment_model import PaymentStatus, PaymentTypeCode
from app.features.wallet.wallet_schemas import WalletResponse
from app.features.quarter.quarter_schemas import QuarterListResponse
from app.features.tournament.tournament_schemas import TournamentListResponse
from app.features.training.training_schemas import TrainingListResponse


class PaymentCreate(CrudCreateSchema):
    sender_wallet_id: uuid.UUID
    receiver_wallet_id: uuid.UUID
    payment_type: PaymentTypeCode
    amount: Decimal = Field(..., gt=0, decimal_places=2)
    status: PaymentStatus = PaymentStatus.PENDING
    description: Optional[str] = None
    quarter_id: Optional[int] = None
    tournament_id: Optional[int] = None
    training_id: Optional[int] = None

    @model_validator(mode="after")
    def _exactly_one_context_at_most(self) -> "PaymentCreate":
        # Structural check only: a payment belongs to at most one business
        # context. The type-based rule ("this payment type *requires* a
        # quarter/tournament/training id") is driven by PAYMENT_TYPE_SPECS and
        # enforced in PaymentService.create().
        provided = [
            name
            for name, value in (
                ("quarter_id", self.quarter_id),
                ("tournament_id", self.tournament_id),
                ("training_id", self.training_id),
            )
            if value is not None
        ]
        if len(provided) > 1:
            raise ValueError(
                f"A payment may reference at most one context; got {provided}."
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
    quarter_id: Optional[int] = None
    tournament_id: Optional[int] = None
    training_id: Optional[int] = None
    created_at: Optional[datetime] = None
    sender_wallet: Optional[WalletResponse] = None
    receiver_wallet: Optional[WalletResponse] = None
    quarter: Optional[QuarterListResponse] = None
    tournament: Optional[TournamentListResponse] = None
    training: Optional[TrainingListResponse] = None
    model_config = ConfigDict(from_attributes=True)


class PaymentFilters(CrudFilters):
    wallet_id: Optional[uuid.UUID] = None
    sender_wallet_id: Optional[uuid.UUID] = None
    receiver_wallet_id: Optional[uuid.UUID] = None
    payment_type: Optional[PaymentTypeCode] = None
    status: Optional[PaymentStatus] = None
    amount__gte: Optional[Decimal] = None
    amount__lte: Optional[Decimal] = None
    quarter_id: Optional[int] = None
    tournament_id: Optional[int] = None
    training_id: Optional[int] = None



