# ============================================
# TRAINING SCHEMAS - Data Validation
# ============================================

from pydantic import ConfigDict
from datetime import date, time
from typing import List, Optional

from app.common.crud.crud_schemas import CrudCreateSchema, CrudFilters, CrudResponseSchema, CrudUpdateSchema
from app.features.training.training_model import TrainingStatus
from app.features.quarter.quarter_model import QuarterType
from app.features.company.company_schemas import CompanyListResponse
from app.features.training_segments.training_segments_schemas import TrainingSegmentResponse


class TrainingCreate(CrudCreateSchema):
    company_id: int
    pool_id: int
    training_date: date
    start_time: time
    end_time: time
    price: int
    status: TrainingStatus = TrainingStatus.INCOMING
    model_config = ConfigDict(from_attributes=True)


class TrainingUpdate(CrudUpdateSchema):
    company_id: Optional[int] = None
    pool_id: Optional[int] = None
    training_date: Optional[date] = None
    start_time: Optional[time] = None
    end_time: Optional[time] = None
    price: Optional[int] = None
    status: Optional[TrainingStatus] = None
    model_config = ConfigDict(from_attributes=True)


class TrainingListResponse(CrudResponseSchema):
    """Lightweight schema for list view."""

    company_id: int
    training_date: date
    start_time: time
    end_time: time
    price: int
    status: TrainingStatus
    number_of_players: int = 0
    quarter_id: Optional[int] = None
    quarter_type: Optional[QuarterType] = None
    company: Optional[CompanyListResponse] = None
    pool: Optional[CompanyListResponse] = None

    model_config = ConfigDict(from_attributes=True)


class TrainingResponse(CrudResponseSchema):
    """Full schema for get by id — includes nested pool, player count and the
    ordered segment timeline."""

    company_id: int
    training_date: date
    start_time: time
    end_time: time
    price: int
    status: TrainingStatus
    number_of_players: int = 0
    quarter_id: Optional[int] = None
    quarter_type: Optional[QuarterType] = None
    company: Optional[CompanyListResponse] = None
    pool: Optional[CompanyListResponse] = None
    segments: List[TrainingSegmentResponse] = []

    model_config = ConfigDict(from_attributes=True)


class TrainingFilters(CrudFilters):
    """
    Pagination (inherited from CrudFilters):
        page               → default 1
        size               → default 20, max 100
    """
    company_id: Optional[int] = None
    user_id: Optional[int] = None
    pool_id: Optional[int] = None
    status: Optional[TrainingStatus] = None
    training_date__gte: Optional[date] = None
    training_date__lte: Optional[date] = None
