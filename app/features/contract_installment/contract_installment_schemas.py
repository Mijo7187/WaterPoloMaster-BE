# ============================================
# CONTRACT INSTALLMENT SCHEMAS - Data Validation
# ============================================

from datetime import date
from decimal import Decimal
from typing import Optional

from pydantic import ConfigDict, Field

from app.common.crud.crud_schemas import (
    CrudCreateSchema,
    CrudFilters,
    CrudResponseSchema,
    CrudUpdateSchema,
)


class ContractInstallmentCreate(CrudCreateSchema):
    contract_id: int
    period_start: date
    period_end: date
    due_date: date
    # 0 is allowed (a scholarship) — billing skips 0-amount rows.
    amount: Decimal = Field(..., ge=0, decimal_places=2)
    waived: bool = False
    model_config = ConfigDict(from_attributes=True)


class ContractInstallmentItem(CrudCreateSchema):
    """One entry of a contract's `installments_list` at create.

    Same fields as ContractInstallmentCreate minus contract_id — the contract
    does not exist yet. amount may be 0 (a scholarship).
    """
    period_start: date
    period_end: date
    due_date: date
    amount: Decimal = Field(..., ge=0, decimal_places=2)
    waived: bool = False
    model_config = ConfigDict(from_attributes=True)


class ContractInstallmentUpdate(CrudUpdateSchema):
    period_start: Optional[date] = None
    period_end: Optional[date] = None
    due_date: Optional[date] = None
    amount: Optional[Decimal] = Field(None, ge=0, decimal_places=2)
    waived: Optional[bool] = None
    model_config = ConfigDict(from_attributes=True)


class ContractInstallmentListResponse(CrudResponseSchema):
    """The shape a payment's resolved `payable` takes when payable_type is
    contract_installment, and the `installments` on a contract.

    Deliberately WITHOUT paid_amount / payment_status. That path does not
    run attach_payment_state, so declaring the fields here would report a
    truthful-looking `paid_amount: 0` on every installment reached through
    them. The list endpoint uses ContractInstallmentResponse instead, which
    does get the state attached.
    """

    contract_id: int
    period_start: date
    period_end: date
    due_date: date
    amount: Decimal
    waived: bool

    model_config = ConfigDict(from_attributes=True)


class ContractInstallmentResponse(CrudResponseSchema):
    """Full schema for get by id.

    `paid_amount` / `payment_status` are COMPUTED from the payments pointing at
    this installment — paid/pending/partial is never stored. `waived` is the
    only stored payment-state.
    """

    contract_id: int
    period_start: date
    period_end: date
    due_date: date
    amount: Decimal
    waived: bool
    paid_amount: Decimal = Decimal("0")
    payment_status: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class ContractInstallmentFilters(CrudFilters):
    """
    Pagination (inherited from CrudFilters):
        page               → default 1
        size               → default 20, max 100
    """
    contract_id: Optional[int] = None
    waived: Optional[bool] = None
    due_date__gte: Optional[date] = None
    due_date__lte: Optional[date] = None
