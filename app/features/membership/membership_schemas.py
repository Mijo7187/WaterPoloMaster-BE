# ============================================
# MEMBERSHIP SCHEMAS - Data Validation
# ============================================

from decimal import Decimal
from typing import Optional

from pydantic import ConfigDict, Field, computed_field

from app.common.crud.crud_schemas import (
    CrudCreateSchema,
    CrudFilters,
    CrudResponseSchema,
    CrudUpdateSchema,
)
from app.features.membership.membership_model import Program


class MembershipCreate(CrudCreateSchema):
    company_id: int
    name: str = Field(..., min_length=1, max_length=255)
    program: Program
    months_count: int = Field(..., ge=1)
    price_month: Decimal = Field(..., gt=0, decimal_places=2)
    installments_count: int = Field(1, ge=1)
    is_active: bool = True

    model_config = ConfigDict(from_attributes=True)


class MembershipUpdate(CrudUpdateSchema):
    company_id: Optional[int] = None
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    program: Optional[Program] = None
    months_count: Optional[int] = Field(None, ge=1)
    price_month: Optional[Decimal] = Field(None, gt=0, decimal_places=2)
    installments_count: Optional[int] = Field(None, ge=1)
    is_active: Optional[bool] = None

    model_config = ConfigDict(from_attributes=True)


class MembershipListResponse(CrudResponseSchema):
    """Lightweight schema for list view."""

    company_id: int
    name: str
    program: Program
    months_count: int
    price_month: Decimal
    installments_count: int
    is_active: bool

    @computed_field
    @property
    def price_total(self) -> Decimal:
        """What the whole term costs — saves every client doing the multiply."""
        return self.price_month * self.months_count

    model_config = ConfigDict(from_attributes=True)


class MembershipResponse(CrudResponseSchema):
    """Full schema for get by id."""

    company_id: int
    name: str
    program: Program
    months_count: int
    price_month: Decimal
    installments_count: int
    is_active: bool

    @computed_field
    @property
    def price_total(self) -> Decimal:
        return self.price_month * self.months_count

    model_config = ConfigDict(from_attributes=True)


class MembershipFilters(CrudFilters):
    """
    Pagination (inherited from CrudFilters):
        page               → default 1
        size               → default 20, max 100
    """
    company_id: Optional[int] = None
    program: Optional[Program] = None
    name__ilike: Optional[str] = None
    months_count: Optional[int] = None
    is_active: Optional[bool] = None
