import uuid
from datetime import datetime
from decimal import Decimal
from typing import Optional

from pydantic import ConfigDict, Field

from app.common.crud.crud_schemas import CrudCreateSchema, CrudFilters, CrudResponseSchema, CrudUpdateSchema
from app.features.payment.payment_model import PaymentStatus


class PaymentCreate(CrudCreateSchema):
    sender_wallet_id: uuid.UUID
    receiver_wallet_id: uuid.UUID
    payment_type_id: int
    amount: Decimal = Field(..., gt=0, decimal_places=2)
    status: PaymentStatus = PaymentStatus.PENDING
    description: Optional[str] = None


class PaymentUpdate(CrudUpdateSchema):
    status: Optional[PaymentStatus] = None


class PaymentResponse(CrudResponseSchema):
    id: uuid.UUID
    sender_wallet_id: uuid.UUID
    receiver_wallet_id: uuid.UUID
    payment_type_id: int
    amount: Decimal
    status: PaymentStatus
    description: Optional[str] = None
    created_at: Optional[datetime] = None
    model_config = ConfigDict(from_attributes=True)


class PaymentFilters(CrudFilters):
    sender_wallet_id: Optional[uuid.UUID] = None
    receiver_wallet_id: Optional[uuid.UUID] = None
    payment_type_id: Optional[int] = None
    status: Optional[PaymentStatus] = None
    amount__gte: Optional[Decimal] = None
    amount__lte: Optional[Decimal] = None



