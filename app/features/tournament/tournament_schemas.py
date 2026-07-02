# ============================================
# TOURNAMENT SCHEMAS - Data Validation
# ============================================

from pydantic import ConfigDict
from datetime import date
from typing import Optional

from app.common.crud.crud_schemas import CrudCreateSchema, CrudFilters, CrudResponseSchema, CrudUpdateSchema
from app.features.company.company_schemas import CompanyListResponse


class TournamentCreate(CrudCreateSchema):
    company_id: int
    pool_id: int
    from_date: date
    to_date: date
    price: int
    description: Optional[str] = None
    model_config = ConfigDict(from_attributes=True)


class TournamentUpdate(CrudUpdateSchema):
    company_id: Optional[int] = None
    pool_id: Optional[int] = None
    from_date: Optional[date] = None
    to_date: Optional[date] = None
    price: Optional[int] = None
    description: Optional[str] = None
    model_config = ConfigDict(from_attributes=True)


class TournamentListResponse(CrudResponseSchema):
    """Lightweight schema for list view."""

    company_id: int
    pool_id: int
    from_date: date
    to_date: date
    price: int
    description: Optional[str] = None
    number_of_users: int = 0
    company: Optional[CompanyListResponse] = None
    pool: Optional[CompanyListResponse] = None

    model_config = ConfigDict(from_attributes=True)


class TournamentResponse(CrudResponseSchema):
    """Full schema for get by id."""

    company_id: int
    pool_id: int
    from_date: date
    to_date: date
    price: int
    description: Optional[str] = None
    number_of_users: int = 0
    company: Optional[CompanyListResponse] = None
    pool: Optional[CompanyListResponse] = None

    model_config = ConfigDict(from_attributes=True)


class TournamentFilters(CrudFilters):
    """
    Pagination (inherited from CrudFilters):
        page               → default 1
        size               → default 20, max 100
    """
    company_id: Optional[int] = None
    pool_id: Optional[int] = None
    from_date__gte: Optional[date] = None
    to_date__lte: Optional[date] = None
