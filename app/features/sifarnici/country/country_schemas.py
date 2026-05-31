# ============================================
# COUNTRY SCHEMAS - Data Validation
# ============================================

from typing import Optional

from pydantic import Field

from app.common.crud.crud_schemas import (
    CrudCreateSchema,
    CrudFilters,
    CrudUpdateSchema,
    CrudResponseSchema,
)


class CountryCreate(CrudCreateSchema):
    name: str = Field(..., min_length=1, max_length=255)
    is_active: bool = True


class CountryUpdate(CrudUpdateSchema):
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    is_active: Optional[bool] = None


class CountryResponse(CrudResponseSchema):
    name: str
    is_active: bool


class CountryListResponse(CrudResponseSchema):
    name: str
    is_active: bool


class CountryFilters(CrudFilters):
    name__ilike: Optional[str] = None
    is_active: Optional[bool] = None
