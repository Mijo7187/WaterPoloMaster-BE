# ============================================
# SEASON SCHEMAS - Data Validation
# ============================================

from datetime import date
from typing import Optional

from pydantic import ConfigDict

from app.common.crud.crud_schemas import (
    CrudCreateSchema,
    CrudFilters,
    CrudResponseSchema,
    CrudUpdateSchema,
)
from app.features.company.company_schemas import CompanyListResponse


class SeasonCreate(CrudCreateSchema):
    company_id: int
    name: str
    start_date: date
    end_date: date
    is_current: bool = False
    model_config = ConfigDict(from_attributes=True)


class SeasonUpdate(CrudUpdateSchema):
    company_id: Optional[int] = None
    name: Optional[str] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    is_current: Optional[bool] = None
    model_config = ConfigDict(from_attributes=True)


class SeasonListResponse(CrudResponseSchema):
    """Lightweight schema for list view."""

    company_id: int
    name: str
    start_date: date
    end_date: date
    is_current: bool

    model_config = ConfigDict(from_attributes=True)


class SeasonResponse(CrudResponseSchema):
    """Full schema for get by id."""

    company_id: int
    name: str
    start_date: date
    end_date: date
    is_current: bool
    company: Optional[CompanyListResponse] = None

    model_config = ConfigDict(from_attributes=True)


class SeasonFilters(CrudFilters):
    """
    Pagination (inherited from CrudFilters):
        page               → default 1
        size               → default 20, max 100
    """
    company_id: Optional[int] = None
    name__ilike: Optional[str] = None
    is_current: Optional[bool] = None
    start_date__gte: Optional[date] = None
    end_date__lte: Optional[date] = None
