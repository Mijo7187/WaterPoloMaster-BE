# ============================================
# GROUP SERVICE - Business Logic
# ============================================

from datetime import date
from typing import Any, Optional

from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.common.crud.crud_service import CrudService
from app.core.api.exceptions import (
    BadRequestException,
    ConflictException,
    ForbiddenException,
    NotFoundException,
)
from app.features.group.group_model import Group
from app.features.group.group_repository import GroupRepository
from app.features.group.group_schemas import GroupCreate


def academy_of(company) -> Optional[int]:
    """The academy a company belongs to, or the company itself.

    Seasons are usually owned by the ACADEMY while selections belong to its
    member clubs, so "same company" is too strict a test for a group. A
    company with no academy stands alone and is its own academy.
    """
    if company is None:
        return None
    return company.academy_id or company.id


def resolve_group_season_id(db, group_id: int, company_id: int, d: date) -> int:
    """The season a group-scoped training/tournament belongs to.

    A group already fixes its season, so there is nothing to look up by date —
    and season_service.resolve_season_id would be wrong here anyway: it matches
    Season.company_id against the club, while an academy's seasons are owned by
    the academy. This validates the pairing instead and hands back the group's
    own season, which is what keeps the stored season_id from ever drifting
    away from the group the row points at.
    """
    repository = GroupRepository(db)

    group = repository.get_by_id(group_id)
    if group is None:
        raise NotFoundException("Group not found")

    season = group.season

    # Same ACADEMY, not necessarily the same company — see academy_of.
    academies = {
        academy_of(repository.get_company(company_id)),
        academy_of(repository.get_company(season.company_id)),
    }
    if len(academies) != 1 or None in academies:
        raise BadRequestException(
            "Group and company must belong to the same academy."
        )

    if not season.start_date <= d <= season.end_date:
        raise BadRequestException(
            f"Date {d} is outside the group's season "
            f"({season.start_date} - {season.end_date})."
        )

    return season.id


class GroupService(CrudService[Group]):
    def __init__(self, db: Session):
        super().__init__(db, GroupRepository(db))

    def _validate(self, season_id: int, selection_id: int):
        season = self.repository.get_season(season_id)
        if season is None:
            raise NotFoundException("Season not found")
        selection = self.repository.get_selection(selection_id)
        if selection is None:
            raise NotFoundException("Selection not found")

        # Same ACADEMY, not necessarily the same company: an academy-level
        # season legitimately pairs with a club-level selection.
        academies = {
            academy_of(self.repository.get_company(season.company_id)),
            academy_of(self.repository.get_company(selection.company_id)),
        }
        if len(academies) != 1 or None in academies:
            raise BadRequestException(
                "Season and selection must belong to the same academy."
            )

        if not selection.is_active:
            raise BadRequestException("Selection is not active.")

        return season, selection

    def create(self, schema: BaseModel, current_user: Optional[Any] = None) -> Group:
        season, _ = self._validate(schema.season_id, schema.selection_id)

        # None → SUPER_ADMIN or internal call, unrestricted.
        company_id = self.company_scope_for(current_user)
        if company_id is not None and season.company_id != company_id:
            raise ForbiddenException("You can only manage records in your own company.")

        if self.repository.find(schema.season_id, schema.selection_id):
            raise ConflictException("This group already exists for that season.")

        return super().create(schema, current_user=current_user)

    def get_or_create(self, season_id: int, selection_id: int) -> Group:
        """The group for (season, selection), created if this is its first use.

        Signing the first player of a squad is what brings the squad into
        existence, so the auto-enrol on MEMBERSHIP contract create does not
        need an admin to have set it up first. Internal call — company scoping
        does not apply, but the academy and active-selection checks still run.
        """
        existing = self.repository.find(season_id, selection_id)
        if existing:
            return existing

        return self.create(
            GroupCreate(season_id=season_id, selection_id=selection_id),
            current_user=None,
        )

    def delete(self, obj_id: int) -> None:
        if not self.repository.delete(obj_id):
            raise NotFoundException("Group not found")
