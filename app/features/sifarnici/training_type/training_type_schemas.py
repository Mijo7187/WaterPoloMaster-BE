# ============================================
# TRAINING TYPE SCHEMAS - Data Validation
# ============================================

from typing import Optional

from pydantic import Field

from app.common.crud.crud_schemas import (
    CrudCreateSchema,
    CrudFilters,
    CrudUpdateSchema,
    CrudResponseSchema,
)


class TrainingTypeCreate(CrudCreateSchema):
    name: str = Field(..., min_length=1, max_length=255)
    is_active: bool = True
    company_id: int


class TrainingTypeUpdate(CrudUpdateSchema):
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    is_active: Optional[bool] = None
    company_id: Optional[int] = None


class TrainingTypeResponse(CrudResponseSchema):
    name: str
    is_active: bool
    company_id: int


class TrainingTypeListResponse(CrudResponseSchema):
    name: str
    is_active: bool
    company_id: int


class TrainingTypeFilters(CrudFilters):
    name__ilike: Optional[str] = None
    is_active: Optional[bool] = None
    company_id: Optional[int] = None
