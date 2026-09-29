# ============================================
# GROUP USER SERVICE - Business Logic
# ============================================

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
from app.features.group.group_service import academy_of
from app.features.group_user.group_user_model import GroupUser
from app.features.group_user.group_user_repository import GroupUserRepository
from app.features.group_user.group_user_schemas import GroupUserCreate


class GroupUserService(CrudService[GroupUser]):
    def __init__(self, db: Session):
        super().__init__(db, GroupUserRepository(db))

    def create(self, schema: BaseModel, current_user: Optional[Any] = None) -> GroupUser:
        group = self.repository.get_group(schema.group_id)
        if group is None:
            raise NotFoundException("Group not found")
        user = self.repository.get_user(schema.user_id)
        if user is None:
            raise NotFoundException("User not found")

        season = group.season
        if season is None:
            raise NotFoundException("Season not found")

        # The group already guarantees season and selection agree; the player
        # must come from the same academy as the group.
        from app.features.group.group_repository import GroupRepository

        companies = GroupRepository(self.db)
        if academy_of(companies.get_company(season.company_id)) != academy_of(
            companies.get_company(user.company_id)
        ):
            raise BadRequestException(
                "The user must belong to the same academy as the group."
            )

        # None → SUPER_ADMIN or internal call, unrestricted.
        company_id = self.company_scope_for(current_user)
        if company_id is not None and season.company_id != company_id:
            raise ForbiddenException("You can only manage records in your own company.")

        if self.repository.exists(schema.group_id, schema.user_id):
            raise ConflictException("User is already in this group.")

        return super().create(schema, current_user=current_user)

    def enrol_if_absent(self, group_id: int, user_id: int) -> Optional[GroupUser]:
        """Put a user in a group unless they are already in it.

        The idempotent entry point for automatic enrolment (see the MEMBERSHIP
        contract post-save hook). Returns None when the row already exists;
        otherwise creates it as an internal call, so company scoping does not
        apply. Every other validation in `create` still runs.
        """
        if self.repository.exists(group_id, user_id):
            return None

        return self.create(
            GroupUserCreate(group_id=group_id, user_id=user_id),
            current_user=None,
        )

    def delete(self, obj_id: int) -> None:
        if not self.repository.delete(obj_id):
            raise NotFoundException("Group user entry not found")
