# ============================================
# SWIMMING DISCIPLINE SCHEMAS - Data Validation
# ============================================

from typing import Optional

from pydantic import Field

from app.common.crud.crud_schemas import (
    CrudCreateSchema,
    CrudFilters,
    CrudUpdateSchema,
    CrudResponseSchema,
)


class SwimmingDisciplineCreate(CrudCreateSchema):
    name: str = Field(..., min_length=1, max_length=255)
    is_active: bool = True
    company_id: int


class SwimmingDisciplineUpdate(CrudUpdateSchema):
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    is_active: Optional[bool] = None
    company_id: Optional[int] = None


class SwimmingDisciplineResponse(CrudResponseSchema):
    name: str
    is_active: bool
    company_id: int


class SwimmingDisciplineListResponse(CrudResponseSchema):
    name: str
    is_active: bool
    company_id: int


class SwimmingDisciplineFilters(CrudFilters):
    name__ilike: Optional[str] = None
    is_active: Optional[bool] = None
    company_id: Optional[int] = None
