# ============================================
# TRAINING SCHEMAS - Data Validation
# ============================================

from pydantic import ConfigDict, model_validator
from datetime import date, time
from typing import Optional

from app.common.crud.crud_schemas import CrudCreateSchema, CrudFilters, CrudResponseSchema, CrudUpdateSchema
from app.features.training.training_model import TrainingStatus
from app.features.company.company_schemas import CompanyListResponse
from app.features.sifarnici.training_type.training_type_schemas import TrainingTypeListResponse


class TrainingCreate(CrudCreateSchema):
    company_id: int
    pool_id: int
    training_type_id: int
    training_date: date
    start_time: time
    end_time: time
    price: int
    status: TrainingStatus = TrainingStatus.INCOMING
    model_config = ConfigDict(from_attributes=True)


class TrainingUpdate(CrudUpdateSchema):
    company_id: Optional[int] = None
    pool_id: Optional[int] = None
    training_type_id: Optional[int] = None
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
    training_type_id: Optional[int] = None
    company: Optional[CompanyListResponse] = None
    pool: Optional[CompanyListResponse] = None
    training_type: Optional[TrainingTypeListResponse] = None

    model_config = ConfigDict(from_attributes=True)


class TrainingResponse(CrudResponseSchema):
    """Full schema for get by id — includes nested pool and player count."""

    company_id: int
    training_date: date
    start_time: time
    end_time: time
    price: int
    status: TrainingStatus
    number_of_players: int = 0
    training_type_id: Optional[int] = None
    company: Optional[CompanyListResponse] = None
    pool: Optional[CompanyListResponse] = None
    training_type: Optional[TrainingTypeListResponse] = None

    model_config = ConfigDict(from_attributes=True)


class TrainingFilters(CrudFilters):
    """
    Pagination (inherited from CrudFilters):
        page               → default 1
        size               → default 20, max 100
    """
    company_id: Optional[int] = None
    status: Optional[TrainingStatus] = None
    training_date__gte: Optional[date] = None
    training_date__lte: Optional[date] = None
