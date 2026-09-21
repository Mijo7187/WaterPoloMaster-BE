# ============================================
# CONTRACT SCHEMAS - Data Validation
# ============================================

from datetime import date, datetime
from decimal import Decimal
from typing import List, Optional

from pydantic import ConfigDict, Field

from app.common.crud.crud_schemas import (
    CrudCreateSchema,
    CrudFilters,
    CrudResponseSchema,
    CrudUpdateSchema,
)
from app.features.contract.contract_model import ContractStatus, ContractType
from app.features.contract_installment.contract_installment_schemas import (
    ContractInstallmentItem,
    ContractInstallmentResponse,
)
from app.features.membership.membership_schemas import MembershipListResponse
from app.features.users.users_schemas import UserListResponse


class ContractCreate(CrudCreateSchema):
    company_id: int
    user_id: int
    contract_type: ContractType

    # MEMBERSHIP: derived from installments_list when omitted — start_date is
    # the first row's period_start, end_date the last row's period_end — and
    # must match them when sent. STAFF: start_date is required, end_date
    # optional (null = open-ended).
    start_date: Optional[date] = None
    end_date: Optional[date] = None

    # The catalog plan this contract is signed off, if any. MEMBERSHIP only.
    # When installments_list is omitted it is built from the plan (split over
    # `amount` if sent, else the plan's total); anything sent explicitly wins.
    membership_id: Optional[int] = None

    # The agreed amount. For MEMBERSHIP it is the TOTAL for the whole term and
    # must equal sum(installments_list) — omitted, it is derived. For STAFF it
    # is the monthly salary, required and > 0.
    amount: Optional[Decimal] = Field(None, ge=0, decimal_places=2)

    # MEMBERSHIP only — the term's schedule, one contract_installment row per
    # entry, at least one, sorted by period_start and non-overlapping. A
    # scholarship is a row with amount 0. STAFF installments come from the
    # monthly salary job, never from here.
    installments_list: Optional[List[ContractInstallmentItem]] = None

    # Ignored — status is computed from the dates (compute_contract_status).
    # Sending CANCELLED on create is rejected.
    status: Optional[ContractStatus] = None
    signed_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class ContractUpdate(CrudUpdateSchema):
    # start_date / contract_type / membership_id / installments_list are
    # intentionally NOT updatable (ignored if sent) — they fix the direction,
    # the provenance and the installment schedule. Edit single installments
    # via /contract-installment; contract.amount / end_date re-sync from them.
    #
    # MEMBERSHIP: amount / end_date may only be sent if they still match the
    # schedule (sum of installments, last period_end). STAFF: both editable.
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
    amount: Decimal
    start_date: date
    end_date: Optional[date] = None
    status: ContractStatus
    signed_at: Optional[datetime] = None
    user: Optional[UserListResponse] = None
    # The catalog plan this was signed off (provenance only — amount /
    # the installments are the contract's own terms and always win).
    membership: Optional[MembershipListResponse] = None

    model_config = ConfigDict(from_attributes=True)


class ContractResponse(CrudResponseSchema):
    """Full schema for get by id — includes the generated installments."""

    company_id: int
    user_id: int
    membership_id: Optional[int] = None
    contract_type: ContractType
    amount: Decimal
    start_date: date
    end_date: Optional[date] = None
    status: ContractStatus
    signed_at: Optional[datetime] = None
    user: Optional[UserListResponse] = None
    # The catalog plan this was signed off (provenance only — amount /
    # the installments are the contract's own terms and always win).
    membership: Optional[MembershipListResponse] = None
    # With paid_amount / payment_status — ContractService.get_by_id attaches
    # them, so the edit screen needs no second call.
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
    status: Optional[ContractStatus] = None
    start_date__gte: Optional[date] = None
    end_date__lte: Optional[date] = None

    # Not a contract column - handled by ContractRepository._apply_filter as a
    # date overlap with the season's [start_date, end_date]. Includes both
    # MEMBERSHIP and STAFF contracts; narrow with contract_type if needed.
    season_id: Optional[int] = None
