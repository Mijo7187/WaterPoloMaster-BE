# ============================================
# SELECTION SCHEMAS - Data Validation
# ============================================

from typing import Optional

from pydantic import ConfigDict

from app.common.crud.crud_schemas import (
    CrudCreateSchema,
    CrudFilters,
    CrudResponseSchema,
    CrudUpdateSchema,
)


class SelectionCreate(CrudCreateSchema):
    company_id: int
    name: str
    age_min: Optional[int] = None
    age_max: Optional[int] = None
    is_active: bool = True
    model_config = ConfigDict(from_attributes=True)


class SelectionUpdate(CrudUpdateSchema):
    company_id: Optional[int] = None
    name: Optional[str] = None
    age_min: Optional[int] = None
    age_max: Optional[int] = None
    is_active: Optional[bool] = None
    model_config = ConfigDict(from_attributes=True)


class SelectionListResponse(CrudResponseSchema):
    """Lightweight schema for list view."""

    company_id: int
    name: str
    age_min: Optional[int] = None
    age_max: Optional[int] = None
    is_active: bool

    model_config = ConfigDict(from_attributes=True)


class SelectionResponse(CrudResponseSchema):
    """Full schema for get by id."""

    company_id: int
    name: str
    age_min: Optional[int] = None
    age_max: Optional[int] = None
    is_active: bool

    model_config = ConfigDict(from_attributes=True)


class SelectionFilters(CrudFilters):
    """
    Pagination (inherited from CrudFilters):
        page               → default 1
        size               → default 20, max 100
    """
    company_id: Optional[int] = None
    name__ilike: Optional[str] = None
    is_active: Optional[bool] = None
