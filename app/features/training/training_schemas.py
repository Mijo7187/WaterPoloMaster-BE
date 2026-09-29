# ============================================
# TRAINING SCHEMAS - Data Validation
# ============================================

from pydantic import ConfigDict
from datetime import date, time
from decimal import Decimal
from typing import Dict, List, Optional

from app.common.crud.crud_schemas import CrudCreateSchema, CrudFilters, CrudResponseSchema, CrudSummarySchema, CrudUpdateSchema
from app.features.training.training_model import TrainingStatus
from app.utils.dateUtils import QuarterType
from app.features.company.company_schemas import CompanyListResponse
from app.features.group.group_schemas import GroupListResponse, GroupResponse
from app.features.training_segments.training_segments_schemas import TrainingSegmentResponse


class TrainingCreate(CrudCreateSchema):
    company_id: int
    pool_id: int
    training_date: date
    start_time: time
    end_time: time
    price: int
    status: TrainingStatus = TrainingStatus.INCOMING
    # Optional — an open session belongs to no squad. season_id is NOT accepted
    # from the client; it is derived from this group, or from the date.
    group_id: Optional[int] = None
    model_config = ConfigDict(from_attributes=True)


class TrainingUpdate(CrudUpdateSchema):
    company_id: Optional[int] = None
    pool_id: Optional[int] = None
    training_date: Optional[date] = None
    start_time: Optional[time] = None
    end_time: Optional[time] = None
    price: Optional[int] = None
    status: Optional[TrainingStatus] = None
    # Send null to detach the training from its squad.
    group_id: Optional[int] = None
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
    season_id: Optional[int] = None
    group_id: Optional[int] = None
    quarter_type: Optional[QuarterType] = None
    company: Optional[CompanyListResponse] = None
    pool: Optional[CompanyListResponse] = None
    group: Optional[GroupListResponse] = None

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
    season_id: Optional[int] = None
    group_id: Optional[int] = None
    quarter_type: Optional[QuarterType] = None
    company: Optional[CompanyListResponse] = None
    pool: Optional[CompanyListResponse] = None
    group: Optional[GroupResponse] = None
    segments: List[TrainingSegmentResponse] = []

    model_config = ConfigDict(from_attributes=True)


class TrainingFilters(CrudFilters):
    """
        ?group_id=X        → one squad's calendar
        ?group_id__isnull=true → open sessions, belonging to no squad

    Pagination (inherited from CrudFilters):
        page               → default 1
        size               → default 20, max 100
    """
    company_id: Optional[int] = None
    user_id: Optional[int] = None
    pool_id: Optional[int] = None
    season_id: Optional[int] = None
    group_id: Optional[int] = None
    group_id__isnull: Optional[bool] = None
    status: Optional[TrainingStatus] = None
    training_date__gte: Optional[date] = None
    training_date__lte: Optional[date] = None


class TrainingSummary(CrudSummarySchema):
    """Totals over the filtered training list (all pages).

    by_status carries every TrainingStatus value, 0 where none match.
    total_price sums price over non-CANCELLED trainings — what is owed to
    the pool(s) for these sessions.
    """
    count: int
    by_status: Dict[str, int]
    total_price: Decimal
