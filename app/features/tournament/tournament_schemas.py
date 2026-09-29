# ============================================
# TOURNAMENT SCHEMAS - Data Validation
# ============================================

from pydantic import ConfigDict
from datetime import date
from typing import Optional

from app.common.crud.crud_schemas import CrudCreateSchema, CrudFilters, CrudResponseSchema, CrudUpdateSchema
from app.features.company.company_schemas import CompanyListResponse
from app.features.group.group_schemas import GroupListResponse, GroupResponse
from app.utils.dateUtils import QuarterType


class TournamentCreate(CrudCreateSchema):
    company_id: int
    pool_id: int
    from_date: date
    to_date: date
    price: int
    description: Optional[str] = None
    # Optional — a club-wide tournament belongs to no single squad. season_id is
    # NOT accepted from the client; it is derived from this group, or from_date.
    group_id: Optional[int] = None
    model_config = ConfigDict(from_attributes=True)


class TournamentUpdate(CrudUpdateSchema):
    company_id: Optional[int] = None
    pool_id: Optional[int] = None
    from_date: Optional[date] = None
    to_date: Optional[date] = None
    price: Optional[int] = None
    description: Optional[str] = None
    # Send null to detach the tournament from its squad.
    group_id: Optional[int] = None
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
    season_id: Optional[int] = None
    group_id: Optional[int] = None
    quarter_type: Optional[QuarterType] = None
    company: Optional[CompanyListResponse] = None
    pool: Optional[CompanyListResponse] = None
    group: Optional[GroupListResponse] = None

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
    season_id: Optional[int] = None
    group_id: Optional[int] = None
    quarter_type: Optional[QuarterType] = None
    company: Optional[CompanyListResponse] = None
    pool: Optional[CompanyListResponse] = None
    group: Optional[GroupResponse] = None

    model_config = ConfigDict(from_attributes=True)


class TournamentFilters(CrudFilters):
    """
        ?group_id=X        → one squad's tournaments
        ?group_id__isnull=true → tournaments belonging to no squad

    Pagination (inherited from CrudFilters):
        page               → default 1
        size               → default 20, max 100
    """
    company_id: Optional[int] = None
    user_id: Optional[int] = None
    pool_id: Optional[int] = None
    season_id: Optional[int] = None
    group_id: Optional[int] = None
    group_id__isnull: Optional[bool] = None
    from_date__gte: Optional[date] = None
    to_date__lte: Optional[date] = None
