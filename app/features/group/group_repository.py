# ============================================
# GROUP REPOSITORY - Database Operations
# ============================================

from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.common.crud.crud_repository import CrudRepository
from app.features.company.company_model import Company
from app.features.group.group_model import Group
from app.features.season.season_model import Season
from app.features.sifarnici.selection.selection_model import Selection


class GroupRepository(CrudRepository[Group]):
    def __init__(self, db: Session):
        super().__init__(db, Group)

    def company_scope_clause(self, company_id: int):
        """No company_id column — a group belongs to its season's company."""
        return Group.season_id.in_(
            select(Season.id).where(Season.company_id == company_id)
        )

    def get_list_relations(self):
        return [
            lambda: selectinload(Group.season),
            lambda: selectinload(Group.selection),
        ]

    def get_by_id_relations(self):
        return [
            lambda: selectinload(Group.season),
            lambda: selectinload(Group.selection),
        ]

    # ── Lookups used by create validation ───────────

    def get_season(self, season_id: int) -> Optional[Season]:
        return self.db.get(Season, season_id)

    def get_selection(self, selection_id: int) -> Optional[Selection]:
        return self.db.get(Selection, selection_id)

    def get_company(self, company_id: int) -> Optional[Company]:
        return self.db.get(Company, company_id)

    def get_current_season_for_company(self, company_id: int) -> Optional[Season]:
        """The company's season flagged is_current, if it has one.

        Drives the auto-enrol on MEMBERSHIP contract create — resolved against
        the ACADEMY, so every club under it shares one set of seasons.
        """
        return (
            self.db.query(Season)
            .filter(Season.company_id == company_id, Season.is_current.is_(True))
            .first()
        )

    def find(self, season_id: int, selection_id: int) -> Optional[Group]:
        return (
            self.db.query(Group)
            .filter(Group.season_id == season_id, Group.selection_id == selection_id)
            .first()
        )

    def delete(self, obj_id: int) -> bool:
        obj = self.db.get(Group, obj_id)
        if obj is None:
            return False
        self.db.delete(obj)
        self.db.commit()
        return True
