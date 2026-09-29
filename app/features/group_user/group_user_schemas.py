# ============================================
# GROUP USER SCHEMAS - Data Validation
# ============================================

from typing import Optional

from pydantic import ConfigDict

from app.common.crud.crud_schemas import CrudCreateSchema, CrudFilters, CrudResponseSchema
from app.features.group.group_schemas import GroupResponse
from app.features.users.users_schemas import UserListResponse


class GroupUserCreate(CrudCreateSchema):
    group_id: int
    user_id: int


class GroupUserResponse(CrudResponseSchema):
    group_id: int
    user_id: int
    # The nested group carries its own season / selection, so one call is
    # enough to say which squad of which season this is.
    group: Optional[GroupResponse] = None
    user: Optional[UserListResponse] = None

    model_config = ConfigDict(from_attributes=True)


class GroupUserFilters(CrudFilters):
    """
        ?group_id=X  → the squad of one group
        ?user_id=Z   → every group a player is in

    Pagination (inherited from CrudFilters):
        page               → default 1
        size               → default 20, max 100
    """
    group_id: Optional[int] = None
    user_id: Optional[int] = None
