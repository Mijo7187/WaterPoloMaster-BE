# ============================================
# MEMBERSHIP SCHEMAS - Data Validation
# ============================================

from decimal import Decimal
from typing import Optional

from pydantic import ConfigDict, Field, model_validator

from app.common.crud.crud_schemas import (
    CrudCreateSchema,
    CrudFilters,
    CrudResponseSchema,
    CrudUpdateSchema,
)
from app.features.membership.membership_model import BillingType, Program
from app.features.sifarnici.selection.selection_schemas import SelectionListResponse


def _check_term_months(billing_type, term_months):
    """TERM needs a block length; MONTHLY must not carry one.

    Shared by the create and update validators. Returns nothing — raises
    ValueError, which Pydantic turns into a 422.
    """
    if billing_type is None:
        return
    if BillingType(billing_type) == BillingType.TERM:
        if term_months is None:
            raise ValueError("term_months is required when billing_type is TERM.")
        if term_months < 1:
            raise ValueError("term_months must be at least 1.")
    elif term_months is not None:
        raise ValueError("term_months must be null when billing_type is MONTHLY.")


class MembershipCreate(CrudCreateSchema):
    company_id: int
    selection_id: int
    program: Program
    billing_type: BillingType
    price: Decimal = Field(..., gt=0, decimal_places=2)
    term_months: Optional[int] = Field(None, ge=1)
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    is_active: bool = True

    model_config = ConfigDict(from_attributes=True)

    @model_validator(mode="after")
    def _validate_term(self):
        _check_term_months(self.billing_type, self.term_months)
        return self


class MembershipUpdate(CrudUpdateSchema):
    company_id: Optional[int] = None
    selection_id: Optional[int] = None
    program: Optional[Program] = None
    billing_type: Optional[BillingType] = None
    price: Optional[Decimal] = Field(None, gt=0, decimal_places=2)
    term_months: Optional[int] = Field(None, ge=1)
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    is_active: Optional[bool] = None

    model_config = ConfigDict(from_attributes=True)

    @model_validator(mode="after")
    def _validate_term(self):
        # Only checkable when billing_type is part of the patch — a partial
        # update cannot see the stored row. The service re-checks the merged
        # result (see _membership_pre_update).
        if self.billing_type is not None:
            _check_term_months(self.billing_type, self.term_months)
        return self


class MembershipListResponse(CrudResponseSchema):
    """Lightweight schema for list view.

    Carries the nested `selection` so a catalog row can be labelled with the
    squad it prices without a second call. Every query that returns this shape
    eager-loads it — see MembershipRepository.get_list_relations and the
    membership chain in ContractRepository, which nests this schema.
    """

    company_id: int
    selection_id: int
    program: Program
    billing_type: BillingType
    price: Decimal
    term_months: Optional[int] = None
    name: Optional[str] = None
    is_active: bool
    selection: Optional[SelectionListResponse] = None

    model_config = ConfigDict(from_attributes=True)


class MembershipResponse(CrudResponseSchema):
    """Full schema for get by id — includes the selection this plan prices."""

    company_id: int
    selection_id: int
    program: Program
    billing_type: BillingType
    price: Decimal
    term_months: Optional[int] = None
    name: Optional[str] = None
    is_active: bool
    selection: Optional[SelectionListResponse] = None

    model_config = ConfigDict(from_attributes=True)


class MembershipFilters(CrudFilters):
    """
    Pagination (inherited from CrudFilters):
        page               → default 1
        size               → default 20, max 100
    """
    company_id: Optional[int] = None
    selection_id: Optional[int] = None
    program: Optional[Program] = None
    billing_type: Optional[BillingType] = None
    is_active: Optional[bool] = None
