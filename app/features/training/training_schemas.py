# ============================================
# TRAINING SCHEMAS - Data Validation
# ============================================

from pydantic import ConfigDict, Field
from datetime import datetime
from typing import Optional, List

from app.common.crud.crud_schemas import CrudCreateSchema, CrudFilters, CrudResponseSchema, CrudUpdateSchema
from app.features.training.training_model import TrainingStatus
from app.features.users.users_schemas import UserResponse
from app.features.company.company_schemas import CompanyListResponse


class TrainingCreate(CrudCreateSchema):
    company_id: int
    start_training_date_time: datetime
    end_training_date_time: datetime
    price: int
    payed: bool = False
    status: TrainingStatus = TrainingStatus.INCOMING
    users_list: Optional[List[int]] = Field(None, description="List of user IDs")
    model_config = ConfigDict(from_attributes=True)


class TrainingUpdate(CrudUpdateSchema):
    company_id: Optional[int] = None
    start_training_date_time: Optional[datetime] = None
    end_training_date_time: Optional[datetime] = None
    price: Optional[int] = None
    payed: Optional[bool] = None
    status: Optional[TrainingStatus] = None
    users_list: Optional[List[int]] = Field(None, description="List of user IDs")
    model_config = ConfigDict(from_attributes=True)


class TrainingListResponse(CrudResponseSchema):
    """Lightweight schema for list view."""


    company_id: int
    start_training_date_time: datetime
    end_training_date_time: datetime
    price: int
    payed: bool
    status: TrainingStatus
    company: Optional[CompanyListResponse] = None

    model_config = ConfigDict(from_attributes=True)


class TrainingResponse(CrudResponseSchema):
    """Full schema for get by id — includes nested users and pool."""


    company_id: int
    start_training_date_time: datetime
    end_training_date_time: datetime
    price: int
    payed: bool
    status: TrainingStatus
    company: Optional[CompanyListResponse] = None
    pool: Optional[CompanyListResponse] = None
    users: List[UserResponse] = []

    model_config = ConfigDict(from_attributes=True)


class TrainingFilters(CrudFilters):
    """
    Pagination (inherited from CrudFilters):
        page               → default 1
        size               → default 20, max 100
    """
    company_id: Optional[int] = None
    status: Optional[TrainingStatus] = None
    payed: Optional[bool] = None
    start_training_date_time__gte: Optional[datetime] = None
    start_training_date_time__lte: Optional[datetime] = None
