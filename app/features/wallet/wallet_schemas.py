import uuid
from datetime import datetime
from decimal import Decimal
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict

from app.common.crud.crud_schemas import CrudCreateSchema, CrudFilters, CrudResponseSchema, CrudUpdateSchema
from app.features.wallet.wallet_model import WalletOwnerType


class WalletCreate(CrudCreateSchema):
    owner_id: int
    owner_type: WalletOwnerType


class WalletUpdate(CrudUpdateSchema):
    owner_type: Optional[WalletOwnerType] = None


class WalletResponse(CrudResponseSchema):
    id: uuid.UUID
    owner_id: int
    owner_type: WalletOwnerType
    created_at: Optional[datetime] = None
    model_config = ConfigDict(from_attributes=True)


class WalletSummaryResponse(BaseModel):
    balance: Decimal
    total_in_completed: Decimal
    total_out_completed: Decimal
    total_in_pending: Decimal
    total_out_pending: Decimal
    model_config = ConfigDict(from_attributes=True)


class LedgerEntry(BaseModel):
    id: uuid.UUID
    source: Literal["payment"]
    direction: Literal["IN", "OUT"]
    amount: Decimal
    counterparty_wallet_id: Optional[uuid.UUID] = None
    occurred_at: datetime
    description: Optional[str] = None
    model_config = ConfigDict(from_attributes=True)


class WalletFilters(CrudFilters):
    owner_id: Optional[int] = None
    owner_type: Optional[WalletOwnerType] = None
