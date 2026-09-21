# ============================================
# EXERCISE OPTION SCHEMAS - Data Validation
# ============================================

from typing import Optional

from pydantic import Field, field_validator

from app.common.crud.crud_schemas import (
    CrudCreateSchema,
    CrudFilters,
    CrudUpdateSchema,
    CrudResponseSchema,
)
from app.features.training_segments.training_segments_model import SegmentType


class ExerciseOptionCreate(CrudCreateSchema):
    company_id: int
    segment_type: SegmentType
    code: Optional[str] = Field(None, min_length=1, max_length=100)
    name: str = Field(..., min_length=1, max_length=255)
    is_active: bool = True


class ExerciseOptionUpdate(CrudUpdateSchema):
    company_id: Optional[int] = None
    segment_type: Optional[SegmentType] = None
    code: Optional[str] = Field(None, min_length=1, max_length=100)
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    is_active: Optional[bool] = None


class ExerciseOptionResponse(CrudResponseSchema):
    company_id: int
    segment_type: SegmentType
    code: Optional[str] = None
    name: str
    is_active: bool


class ExerciseOptionListResponse(CrudResponseSchema):
    company_id: int
    segment_type: SegmentType
    code: Optional[str] = None
    name: str
    is_active: bool


class ExerciseOptionFilters(CrudFilters):
    company_id: Optional[int] = None
    segment_type: Optional[SegmentType] = None
    name__ilike: Optional[str] = None
    is_active: Optional[bool] = None
