from pydantic import ConfigDict
from typing import Optional

from app.common.crud.crud_schemas import CrudCreateSchema, CrudResponseSchema, CrudFilters
from app.features.quarter_users.quarter_users_model import TypeOfTraining
from app.features.users.users_schemas import UserResponse


class QuarterUsersCreate(CrudCreateSchema):
    quarter_id: int
    user_id: int
    type_of_training: TypeOfTraining
    model_config = ConfigDict(from_attributes=True)


class QuarterUsersResponse(CrudResponseSchema):
    quarter_id: int
    user_id: int
    type_of_training: TypeOfTraining
    user: Optional[UserResponse] = None
    model_config = ConfigDict(from_attributes=True)


class QuarterUsersFilters(CrudFilters):
    quarter_id: Optional[int] = None
    user_id: Optional[int] = None
    type_of_training: Optional[TypeOfTraining] = None
