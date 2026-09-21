# ============================================
# SEASON SELECTION USER SCHEMAS - Data Validation
# ============================================

from typing import Optional

from pydantic import ConfigDict

from app.common.crud.crud_schemas import CrudCreateSchema, CrudFilters, CrudResponseSchema
from app.features.season.season_schemas import SeasonListResponse
from app.features.sifarnici.selection.selection_schemas import SelectionListResponse
from app.features.users.users_schemas import UserListResponse


class SeasonSelectionUserCreate(CrudCreateSchema):
    season_id: int
    selection_id: int
    user_id: int


class SeasonSelectionUserResponse(CrudResponseSchema):
    season_id: int
    selection_id: int
    user_id: int
    season: Optional[SeasonListResponse] = None
    selection: Optional[SelectionListResponse] = None
    user: Optional[UserListResponse] = None

    model_config = ConfigDict(from_attributes=True)


class SeasonSelectionUserFilters(CrudFilters):
    """
        ?season_id=X&selection_id=Y  → the squad of one selection in a season
        ?season_id=X&user_id=Z       → every selection a player is in that season

    Pagination (inherited from CrudFilters):
        page               → default 1
        size               → default 20, max 100
    """
    season_id: Optional[int] = None
    selection_id: Optional[int] = None
    user_id: Optional[int] = None
