from pydantic import ConfigDict
from typing import Optional

from app.common.crud.crud_schemas import CrudCreateSchema, CrudResponseSchema, CrudFilters
from app.features.payment.payment_model import PaymentStatus
from app.features.users.users_schemas import UserResponse


class TournamentUsersCreate(CrudCreateSchema):
    tournament_id: int
    user_id: int
    model_config = ConfigDict(from_attributes=True)


class TournamentUsersResponse(CrudResponseSchema):
    tournament_id: int
    user_id: int
    user: Optional[UserResponse] = None
    payment_status: Optional[PaymentStatus] = None  # None = no payment record yet
    model_config = ConfigDict(from_attributes=True)


class TournamentUsersFilters(CrudFilters):
    tournament_id: Optional[int] = None
    user_id: Optional[int] = None
