from typing import Optional

from pydantic import ConfigDict

from app.common.crud.crud_schemas import (
    CrudCreateSchema,
    CrudFilters,
    CrudResponseSchema,
    CrudUpdateSchema,
)
from app.features.sifarnici.payment_type.payment_type_model import PaymentTypeCode
from app.features.wallet.wallet_model import WalletOwnerType


class PaymentTypeCreate(CrudCreateSchema):
    name: str
    code: PaymentTypeCode
    sender_type: WalletOwnerType
    receiver_type: WalletOwnerType
    active: bool = True


class PaymentTypeUpdate(CrudUpdateSchema):
    name: Optional[str] = None
    code: Optional[PaymentTypeCode] = None
    sender_type: Optional[WalletOwnerType] = None
    receiver_type: Optional[WalletOwnerType] = None
    active: Optional[bool] = None


class PaymentTypeResponse(CrudResponseSchema):
    name: str
    code: PaymentTypeCode
    sender_type: WalletOwnerType
    receiver_type: WalletOwnerType
    active: bool
    model_config = ConfigDict(from_attributes=True)


class PaymentTypeListResponse(PaymentTypeResponse):
    pass


class PaymentTypeFilters(CrudFilters):
    name__ilike: Optional[str] = None
    code: Optional[PaymentTypeCode] = None
    sender_type: Optional[WalletOwnerType] = None
    receiver_type: Optional[WalletOwnerType] = None
    active: Optional[bool] = None
