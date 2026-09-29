# ============================================
# CONTRACT SCHEMAS - Data Validation
# ============================================

from datetime import date, datetime
from decimal import Decimal
from typing import Dict, List, Optional

from pydantic import ConfigDict, Field

from app.common.crud.crud_schemas import (
    CrudCreateSchema,
    CrudFilters,
    CrudResponseSchema,
    CrudSummarySchema,
    CrudUpdateSchema,
)
from app.features.contract.contract_model import ContractStatus, ContractType
from app.features.contract_installment.contract_installment_schemas import (
    ContractInstallmentResponse,
)
from app.features.membership.membership_model import BillingType
from app.features.membership.membership_schemas import MembershipListResponse
from app.features.users.users_schemas import UserListResponse


class ContractCreate(CrudCreateSchema):
    company_id: int
    user_id: int
    contract_type: ContractType

    # MEMBERSHIP and STAFF both require start_date. end_date is DERIVED for
    # MEMBERSHIP (null for MONTHLY, start + term_months for TERM) and may only
    # be sent if it matches; for STAFF it is optional (null = open-ended).
    start_date: Optional[date] = None
    end_date: Optional[date] = None

    # REQUIRED for MEMBERSHIP — billing_type, amount and term_months are
    # snapshotted from it at signing. Must be NULL for STAFF.
    membership_id: Optional[int] = None

    # MEMBERSHIP: ignored, taken from the plan's `price`. STAFF: the monthly
    # salary, required and > 0.
    amount: Optional[Decimal] = Field(None, ge=0, decimal_places=2)

    # Ignored — status is computed from the dates (compute_contract_status).
    # Sending CANCELLED on create is rejected.
    status: Optional[ContractStatus] = None
    signed_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class ContractUpdate(CrudUpdateSchema):
    # start_date / contract_type / membership_id / billing_type / term_months
    # are intentionally NOT updatable (ignored if sent) — they fix the
    # direction, the provenance and the billing shape. Edit single installments
    # via /contract-installment; that no longer moves the contract.
    #
    # Setting end_date is how an open-ended MONTHLY contract is closed.
    end_date: Optional[date] = None
    amount: Optional[Decimal] = Field(None, ge=0, decimal_places=2)
    # Only CANCELLED is accepted; any other value is replaced by the status
    # computed from the dates.
    status: Optional[ContractStatus] = None
    signed_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class ContractListResponse(CrudResponseSchema):
    """Lightweight schema for list view."""

    company_id: int
    user_id: int
    membership_id: Optional[int] = None
    contract_type: ContractType
    billing_type: Optional[BillingType] = None
    term_months: Optional[int] = None
    amount: Decimal
    start_date: date
    end_date: Optional[date] = None
    status: ContractStatus
    signed_at: Optional[datetime] = None
    user: Optional[UserListResponse] = None
    # The catalog plan this was signed off (provenance only — the snapshotted
    # billing_type / amount / term_months are the contract's own terms and
    # always win).
    membership: Optional[MembershipListResponse] = None

    model_config = ConfigDict(from_attributes=True)


class ContractResponse(CrudResponseSchema):
    """Full schema for get by id — includes the generated installments."""

    company_id: int
    user_id: int
    membership_id: Optional[int] = None
    contract_type: ContractType
    billing_type: Optional[BillingType] = None
    term_months: Optional[int] = None
    amount: Decimal
    start_date: date
    end_date: Optional[date] = None
    status: ContractStatus
    signed_at: Optional[datetime] = None
    user: Optional[UserListResponse] = None
    # The catalog plan this was signed off (provenance only).
    membership: Optional[MembershipListResponse] = None
    # Machine-generated, never client-sent. With paid_amount / payment_status —
    # ContractService.get_by_id attaches them, so the edit screen needs no
    # second call.
    installments: List[ContractInstallmentResponse] = []

    model_config = ConfigDict(from_attributes=True)


class ContractFilters(CrudFilters):
    """
    Pagination (inherited from CrudFilters):
        page               → default 1
        size               → default 20, max 100
    """
    company_id: Optional[int] = None
    user_id: Optional[int] = None
    membership_id: Optional[int] = None
    contract_type: Optional[ContractType] = None
    billing_type: Optional[BillingType] = None
    status: Optional[ContractStatus] = None
    start_date__gte: Optional[date] = None
    end_date__lte: Optional[date] = None

    # Not a contract column - handled by ContractRepository._apply_filter as a
    # date overlap with the season's [start_date, end_date]. Includes both
    # MEMBERSHIP and STAFF contracts; narrow with contract_type if needed.
    # An open-ended MONTHLY contract (end_date NULL) matches every season from
    # its start_date onward.
    season_id: Optional[int] = None


class ContractSummary(CrudSummarySchema):
    """Totals over the filtered contract list (all pages).

    by_status carries every ContractStatus value, 0 where none match.
    monthly_income / monthly_outcome are the recurring amounts of ACTIVE
    contracts: MEMBERSHIP MONTHLY dues coming in, STAFF salaries going out.
    TERM blocks are one-off and excluded.
    """
    count: int
    by_status: Dict[str, int]
    monthly_income: Decimal
    monthly_outcome: Decimal
