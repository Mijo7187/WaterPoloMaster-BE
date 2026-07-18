# ============================================
# QUARTER SCHEMAS - Data Validation
# ============================================

from pydantic import ConfigDict
from typing import Optional

from app.common.crud.crud_schemas import CrudCreateSchema, CrudFilters, CrudResponseSchema, CrudUpdateSchema
from app.features.quarter.quarter_model import QuarterType
from app.features.company.company_schemas import CompanyListResponse


class QuarterCreate(CrudCreateSchema):
    quarter_type: QuarterType
    year: int
    waterpolo_price: int
    swimming_price: int
    description: Optional[str] = None
    company_id: int
    model_config = ConfigDict(from_attributes=True)


class QuarterUpdate(CrudUpdateSchema):
    quarter_type: Optional[QuarterType] = None
    year: Optional[int] = None
    waterpolo_price: Optional[int] = None
    swimming_price: Optional[int] = None
    description: Optional[str] = None
    company_id: Optional[int] = None
    model_config = ConfigDict(from_attributes=True)


class QuarterListResponse(CrudResponseSchema):
    """Lightweight schema for list view."""

    quarter_type: QuarterType
    year: int
    waterpolo_price: int
    swimming_price: int
    description: Optional[str] = None
    company_id: int
    number_of_waterpolo_users: int = 0
    number_of_swimming_users: int = 0
    company: Optional[CompanyListResponse] = None

    model_config = ConfigDict(from_attributes=True)


class QuarterResponse(CrudResponseSchema):
    """Full schema for get by id."""

    quarter_type: QuarterType
    year: int
    waterpolo_price: int
    swimming_price: int
    description: Optional[str] = None
    company_id: int
    number_of_waterpolo_users: int = 0
    number_of_swimming_users: int = 0
    company: Optional[CompanyListResponse] = None

    model_config = ConfigDict(from_attributes=True)


class QuarterFilters(CrudFilters):
    """
    Pagination (inherited from CrudFilters):
        page               → default 1
        size               → default 20, max 100
    """
    quarter_type: Optional[QuarterType] = None
    year: Optional[int] = None
    company_id: Optional[int] = None
    user_id: Optional[int] = None
