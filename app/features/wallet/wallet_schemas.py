import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any, Literal, Optional

from pydantic import BaseModel, ConfigDict, model_validator

from app.common.crud.crud_schemas import CrudCreateSchema, CrudFilters, CrudResponseSchema, CrudUpdateSchema
from app.features.wallet.wallet_model import WalletOwnerType


def _owner_response_schemas() -> dict:
    """Which schema serializes a resolved wallet owner, keyed by owner type.

    Imported lazily: users_schemas and company_schemas both import THIS module,
    so a top-level import here would be circular.
    """
    from app.features.company.company_schemas import CompanyListResponse
    from app.features.users.users_schemas import UserListResponse

    return {
        WalletOwnerType.USER: UserListResponse,
        WalletOwnerType.COMPANY: CompanyListResponse,
    }


class WalletCreate(CrudCreateSchema):
    owner_id: int
    owner_type: WalletOwnerType
    name: Optional[str] = None


class WalletUpdate(CrudUpdateSchema):
    owner_type: Optional[WalletOwnerType] = None


class WalletResponse(CrudResponseSchema):
    id: uuid.UUID
    owner_id: int
    owner_type: WalletOwnerType
    name: Optional[str] = None
    created_at: Optional[datetime] = None

    # owner_id is polymorphic and carries no FK, so the owner is attached by the
    # batch resolver before serialization (wallet list / get-by-id). Stays None
    # where nothing resolved it — e.g. wallets nested inside a payment.
    owner: Optional[Any] = None

    model_config = ConfigDict(from_attributes=True)

    @model_validator(mode="after")
    def _serialize_owner(self) -> "WalletResponse":
        """Narrow the raw resolved ORM owner to its list-schema dict.

        An unresolved or orphaned owner (target deleted, wallet remains) stays
        None rather than raising.
        """
        if self.owner is None or isinstance(self.owner, dict):
            return self

        schema = _owner_response_schemas().get(self.owner_type)
        if schema is None:
            self.owner = None
            return self

        self.owner = schema.model_validate(self.owner).model_dump()
        return self


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
