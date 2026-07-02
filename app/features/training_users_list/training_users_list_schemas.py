from pydantic import ConfigDict
from typing import Optional

from app.common.crud.crud_schemas import CrudCreateSchema, CrudResponseSchema, CrudFilters
from app.features.users.users_schemas import UserResponse


class TrainingUsersListCreate(CrudCreateSchema):
    training_id: int
    user_id: int
    model_config = ConfigDict(from_attributes=True)


class TrainingUsersListResponse(CrudResponseSchema):
    training_id: int
    user_id: int
    user: Optional[UserResponse] = None
    model_config = ConfigDict(from_attributes=True)


class TrainingUsersListFilters(CrudFilters):
    training_id: Optional[int] = None
    user_id: Optional[int] = None
