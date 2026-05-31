# ============================================
# CITY SCHEMAS - Data Validation
# ============================================

from pydantic import ConfigDict, Field
from typing import Optional

from app.common.crud.crud_schemas import (
    CrudCreateSchema,
    CrudFilters,
    CrudUpdateSchema,
    CrudResponseSchema,
)
from app.features.sifarnici.country.country_schemas import CountryResponse


class CityCreate(CrudCreateSchema):
    name: str = Field(..., min_length=1, max_length=255)
    is_active: bool = True
    country_id: int
    


class CityUpdate(CrudUpdateSchema):
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    is_active: Optional[bool] = None
    country_id: Optional[int] = None
    


class CityListResponse(CrudResponseSchema):
    """Lightweight schema for list view — includes nested country."""

    name: str
    is_active: bool
    country: Optional[CountryResponse] = None
    model_config = ConfigDict(from_attributes=True)


class CityResponse(CrudResponseSchema):
    """Full schema for get by id — includes all fields."""

    name: str
    is_active: bool
    country_id: int
    country: CountryResponse
    model_config = ConfigDict(from_attributes=True)


class CityFilters(CrudFilters):
    """
    Pagination (inherited from CrudFilters):
        page               → default 1
        size               → default 20, max 100
    """
    name__ilike: Optional[str] = None
    is_active: Optional[bool] = None
    country_id: Optional[int] = None
    
