# ============================================
# GROUP SCHEMAS - Data Validation
# ============================================

from typing import Optional

from pydantic import ConfigDict

from app.common.crud.crud_schemas import CrudCreateSchema, CrudFilters, CrudResponseSchema
from app.features.season.season_schemas import SeasonListResponse
from app.features.sifarnici.selection.selection_schemas import SelectionListResponse


class GroupCreate(CrudCreateSchema):
    season_id: int
    selection_id: int


class GroupListResponse(CrudResponseSchema):
    """Lightweight schema for list view and for nesting inside a group_user,
    a training or a tournament.

    `selection` stays None unless the caller's repository eager-loads it — it
    is here so a training list can print "U15" without a second round trip.
    """

    season_id: int
    selection_id: int
    selection: Optional[SelectionListResponse] = None

    model_config = ConfigDict(from_attributes=True)


class GroupResponse(CrudResponseSchema):
    season_id: int
    selection_id: int
    season: Optional[SeasonListResponse] = None
    selection: Optional[SelectionListResponse] = None

    model_config = ConfigDict(from_attributes=True)


class GroupFilters(CrudFilters):
    """
        ?season_id=X  → every group in a season
        ?selection_id=Y → the same selection across seasons

    Pagination (inherited from CrudFilters):
        page               → default 1
        size               → default 20, max 100
    """
    season_id: Optional[int] = None
    selection_id: Optional[int] = None
