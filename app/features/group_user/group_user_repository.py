# ============================================
# GROUP USER REPOSITORY - Database Operations
# ============================================

from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.common.crud.crud_repository import CrudRepository
from app.features.group.group_model import Group
from app.features.group_user.group_user_model import GroupUser
from app.features.season.season_model import Season
from app.features.users.users_models import User


class GroupUserRepository(CrudRepository[GroupUser]):
    def __init__(self, db: Session):
        super().__init__(db, GroupUser)

    def company_scope_clause(self, company_id: int):
        """No company_id column — a row belongs to its group's season's company."""
        return GroupUser.group_id.in_(
            select(Group.id).where(
                Group.season_id.in_(
                    select(Season.id).where(Season.company_id == company_id)
                )
            )
        )

    def get_list_relations(self):
        return [
            lambda: selectinload(GroupUser.group).selectinload(Group.season),
            lambda: selectinload(GroupUser.group).selectinload(Group.selection),
            lambda: selectinload(GroupUser.user),
        ]

    def get_by_id_relations(self):
        return self.get_list_relations()

    # ── Lookups used by create validation ───────────

    def get_group(self, group_id: int) -> Optional[Group]:
        return self.db.get(Group, group_id)

    def get_user(self, user_id: int) -> Optional[User]:
        return self.db.get(User, user_id)

    def exists(self, group_id: int, user_id: int) -> bool:
        return (
            self.db.query(GroupUser.id)
            .filter(GroupUser.group_id == group_id, GroupUser.user_id == user_id)
            .first()
            is not None
        )

    def delete(self, obj_id: int) -> bool:
        obj = self.db.get(GroupUser, obj_id)
        if obj is None:
            return False
        self.db.delete(obj)
        self.db.commit()
        return True
